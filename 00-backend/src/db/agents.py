import aiosqlite

from src.models import Agent, AgentCreate, AgentUpdate

_COLUMNS = (
    "id, team_id, name, system_prompt, max_output_length_in_words,"
    " context_window_in_tokens, thinking, provider, model,"
    " position, enabled, created_at, updated_at"
)


def _row_to_agent(row: aiosqlite.Row) -> Agent:
    return Agent(**dict(row))


class AgentsRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def create(self, team_id: int, data: AgentCreate) -> Agent:
        position = await self._next_position(team_id)
        cursor = await self._conn.execute(
            "INSERT INTO agents (team_id, name, system_prompt, max_output_length_in_words,"
            " context_window_in_tokens, thinking, provider, model, position, enabled)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                team_id,
                data.name,
                data.system_prompt,
                data.max_output_length_in_words,
                data.context_window_in_tokens,
                # SQLite has no boolean; None has to survive as None, since it
                # means "the engine decides" rather than "off".
                None if data.thinking is None else int(data.thinking),
                data.provider,
                data.model,
                position,
                int(data.enabled),
            ),
        )
        await self._conn.commit()
        agent = await self.get(cursor.lastrowid)
        assert agent is not None
        return agent

    async def get(self, agent_id: int) -> Agent | None:
        async with self._conn.execute(
            f"SELECT {_COLUMNS} FROM agents WHERE id = ?", (agent_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return _row_to_agent(row) if row else None

    async def list_by_team(self, team_id: int) -> list[Agent]:
        async with self._conn.execute(
            f"SELECT {_COLUMNS} FROM agents WHERE team_id = ? ORDER BY position", (team_id,)
        ) as cursor:
            rows = await cursor.fetchall()
        return [_row_to_agent(row) for row in rows]

    async def update(self, agent_id: int, data: AgentUpdate) -> Agent | None:
        fields = data.model_dump(exclude_unset=True)
        if not fields:
            return await self.get(agent_id)

        if "enabled" in fields:
            fields["enabled"] = int(fields["enabled"])
        if fields.get("thinking") is not None:
            fields["thinking"] = int(fields["thinking"])
        assignments = ", ".join(f"{name} = ?" for name in fields)
        await self._conn.execute(
            f"UPDATE agents SET {assignments}, updated_at = datetime('now') WHERE id = ?",
            (*fields.values(), agent_id),
        )
        await self._conn.commit()
        return await self.get(agent_id)

    async def delete(self, agent_id: int) -> bool:
        cursor = await self._conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
        await self._conn.commit()
        return cursor.rowcount > 0

    async def reorder(self, team_id: int, ordered_ids: list[int]) -> list[Agent]:
        """Rewrite the team positions to follow `ordered_ids`.

        The list must hold exactly the team's agents: a partial reorder would
        leave positions ambiguous. Because `(team_id, position)` is an index and
        not a uniqueness constraint, rows are updated one by one with no
        colliding intermediate state.
        """
        current = {agent.id for agent in await self.list_by_team(team_id)}
        if current != set(ordered_ids) or len(ordered_ids) != len(current):
            raise ValueError("The reorder list does not match the team's agents")

        for position, agent_id in enumerate(ordered_ids):
            await self._conn.execute(
                "UPDATE agents SET position = ?, updated_at = datetime('now') WHERE id = ?",
                (position, agent_id),
            )
        await self._conn.commit()
        return await self.list_by_team(team_id)

    async def _next_position(self, team_id: int) -> int:
        async with self._conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM agents WHERE team_id = ?", (team_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return int(row[0])
