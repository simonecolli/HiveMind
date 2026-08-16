import aiosqlite

from src.models import Team, TeamCreate, TeamUpdate

_COLUMNS = (
    "id, name, description, default_max_rounds, synthesis_prompt,"
    " synthesis_max_output_length_in_words, synthesis_provider, synthesis_model,"
    " synthesis_context_window_in_tokens, synthesis_thinking,"
    " protocol, created_at, updated_at"
)


def _row_to_team(row: aiosqlite.Row) -> Team:
    return Team(**dict(row))


class TeamsRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def create(self, data: TeamCreate) -> Team:
        try:
            cursor = await self._conn.execute(
                "INSERT INTO teams (name, description, default_max_rounds, synthesis_prompt,"
                " synthesis_max_output_length_in_words, synthesis_provider, synthesis_model,"
                " synthesis_context_window_in_tokens, synthesis_thinking,"
                " protocol) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    data.name,
                    data.description,
                    data.default_max_rounds,
                    data.synthesis_prompt,
                    data.synthesis_max_output_length_in_words,
                    data.synthesis_provider,
                    data.synthesis_model,
                    data.synthesis_context_window_in_tokens,
                    None
                    if data.synthesis_thinking is None
                    else int(data.synthesis_thinking),
                    data.protocol,
                ),
            )
        except aiosqlite.IntegrityError as exc:
            raise ValueError(f"A team named '{data.name}' already exists") from exc
        await self._conn.commit()
        team = await self.get(cursor.lastrowid)
        assert team is not None
        return team

    async def get(self, team_id: int) -> Team | None:
        async with self._conn.execute(
            f"SELECT {_COLUMNS} FROM teams WHERE id = ?", (team_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return _row_to_team(row) if row else None

    async def list(self) -> list[Team]:
        async with self._conn.execute(
            f"SELECT {_COLUMNS} FROM teams ORDER BY name COLLATE NOCASE"
        ) as cursor:
            rows = await cursor.fetchall()
        return [_row_to_team(row) for row in rows]

    async def update(self, team_id: int, data: TeamUpdate) -> Team | None:
        fields = data.model_dump(exclude_unset=True)
        if not fields:
            return await self.get(team_id)

        if fields.get("synthesis_thinking") is not None:
            fields["synthesis_thinking"] = int(fields["synthesis_thinking"])

        assignments = ", ".join(f"{name} = ?" for name in fields)
        try:
            await self._conn.execute(
                f"UPDATE teams SET {assignments}, updated_at = datetime('now') WHERE id = ?",
                (*fields.values(), team_id),
            )
        except aiosqlite.IntegrityError as exc:
            raise ValueError(f"A team named '{fields.get('name')}' already exists") from exc
        await self._conn.commit()
        return await self.get(team_id)

    async def delete(self, team_id: int) -> bool:
        cursor = await self._conn.execute("DELETE FROM teams WHERE id = ?", (team_id,))
        await self._conn.commit()
        return cursor.rowcount > 0

    async def duplicate(self, team_id: int) -> Team | None:
        source = await self.get(team_id)
        if source is None:
            return None

        copy = await self.create(
            TeamCreate(
                name=await self._free_copy_name(source.name),
                description=source.description,
                default_max_rounds=source.default_max_rounds,
                synthesis_prompt=source.synthesis_prompt,
                synthesis_max_output_length_in_words=(
                    source.synthesis_max_output_length_in_words
                ),
                synthesis_provider=source.synthesis_provider,
                synthesis_model=source.synthesis_model,
                synthesis_context_window_in_tokens=(
                    source.synthesis_context_window_in_tokens
                ),
                synthesis_thinking=source.synthesis_thinking,
                protocol=source.protocol,
            )
        )
        await self._conn.execute(
            "INSERT INTO agents (team_id, name, system_prompt, max_output_length_in_words,"
            " context_window_in_tokens, thinking, provider, model, position, enabled)"
            " SELECT ?, name, system_prompt, max_output_length_in_words,"
            " context_window_in_tokens, thinking, provider, model, position, enabled"
            " FROM agents WHERE team_id = ? ORDER BY position",
            (copy.id, source.id),
        )
        await self._conn.commit()
        return copy

    async def available_name(self, base: str) -> str:
        """`base` when it is free, otherwise the first free copy of it."""
        if not await self._name_taken(base):
            return base
        return await self._free_copy_name(base)

    async def _free_copy_name(self, base: str) -> str:
        """First free name in the series 'X (copy)', 'X (copy 2)', ..."""
        candidate = f"{base} (copy)"
        suffix = 2
        while await self._name_taken(candidate):
            candidate = f"{base} (copy {suffix})"
            suffix += 1
        return candidate

    async def _name_taken(self, name: str) -> bool:
        async with self._conn.execute("SELECT 1 FROM teams WHERE name = ?", (name,)) as cursor:
            return await cursor.fetchone() is not None
