import aiosqlite

from src.graph.deps import StartedTurn
from src.models import Turn

_COLUMNS = (
    "id, agent_id, agent_name, agent_position, pass_no, round, seq, kind, title, text"
)


class SqliteTurnRecorder:
    """SQLite implementation of `TurnRecorder`.

    The row is created when the turn starts because the `turn.start` event has
    to carry a `turn_id` already. If the debate breaks mid-turn, a row with
    partial text survives, which beats losing it.
    """

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def start(
        self,
        *,
        session_id: str,
        agent_id: int,
        agent_name: str,
        agent_position: int,
        pass_no: int,
        round: int,
        kind: str,
    ) -> StartedTurn:
        seq = await self._next_seq(session_id)
        cursor = await self._conn.execute(
            "INSERT INTO turns"
            " (session_id, agent_id, agent_name, agent_position, pass_no, round, seq, kind)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, agent_id, agent_name, agent_position, pass_no, round, seq, kind),
        )
        await self._conn.commit()
        return StartedTurn(int(cursor.lastrowid), seq)

    async def _next_seq(self, session_id: str) -> int:
        async with self._conn.execute(
            "SELECT COALESCE(MAX(seq), -1) + 1 FROM turns WHERE session_id = ?", (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return int(row[0])

    async def finish(self, turn_id: int, text: str, title: str | None) -> None:
        await self._conn.execute(
            "UPDATE turns SET text = ?, title = ? WHERE id = ?", (text, title, turn_id)
        )
        await self._conn.commit()

    async def discard(self, turn_id: int) -> None:
        await self._conn.execute("DELETE FROM turns WHERE id = ?", (turn_id,))
        await self._conn.commit()

    async def list_by_session(self, session_id: str) -> list[Turn]:
        async with self._conn.execute(
            f"SELECT {_COLUMNS} FROM turns WHERE session_id = ? ORDER BY seq", (session_id,)
        ) as cursor:
            rows = await cursor.fetchall()
        return [Turn(**dict(row)) for row in rows]
