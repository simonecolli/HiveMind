import json
import uuid

import aiosqlite

from src.models import Session, SessionCreate, SessionStatus

_COLUMNS = (
    "id, idea, team_id, team_name, max_rounds, team_snapshot, status, error,"
    " created_at, finished_at"
)


def _row_to_session(row: aiosqlite.Row) -> Session:
    fields = dict(row)
    fields["team_snapshot"] = json.loads(fields["team_snapshot"])
    return Session(**fields)


class SessionsRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def create(self, data: SessionCreate) -> Session:
        session_id = str(uuid.uuid4())
        await self._conn.execute(
            "INSERT INTO sessions"
            " (id, idea, team_id, team_name, max_rounds, team_snapshot, status)"
            " VALUES (?, ?, ?, ?, ?, ?, 'running')",
            (
                session_id,
                data.idea,
                data.team_id,
                data.team_name,
                data.max_rounds,
                json.dumps(data.team_snapshot),
            ),
        )
        await self._conn.commit()
        session = await self.get(session_id)
        assert session is not None
        return session

    async def get(self, session_id: str) -> Session | None:
        async with self._conn.execute(
            f"SELECT {_COLUMNS} FROM sessions WHERE id = ?", (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return _row_to_session(row) if row else None

    async def list(self, limit: int = 50) -> list[Session]:
        async with self._conn.execute(
            f"SELECT {_COLUMNS} FROM sessions ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [_row_to_session(row) for row in rows]

    async def finish(
        self, session_id: str, *, status: SessionStatus, error: str | None = None
    ) -> None:
        await self._conn.execute(
            "UPDATE sessions SET status = ?, error = ?, finished_at = datetime('now')"
            " WHERE id = ?",
            (status, error, session_id),
        )
        await self._conn.commit()

    async def mark_running(self, session_id: str) -> None:
        """A follow-up puts the session back in flight."""
        await self._conn.execute(
            "UPDATE sessions SET status = 'running', error = NULL, finished_at = NULL"
            " WHERE id = ?",
            (session_id,),
        )
        await self._conn.commit()

    async def delete(self, session_id: str) -> bool:
        cursor = await self._conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        await self._conn.commit()
        return cursor.rowcount > 0
