"""Who argued which pass of a session.

A session starts with one team and may hand over to another partway through.
Only the handovers are stored: pass 1 is the snapshot already held by the
session, and a pass that names nobody is still being argued by whoever took
over last. Resolving a pass therefore means "the nearest record at or before
it", which is also why the canvas can take a sparse mapping.
"""

import json

import aiosqlite

from src.db.snapshot import snapshot_of, team_from_session, team_from_snapshot
from src.models import Agent, Session, SessionPass, Team

_COLUMNS = "pass_no, team_id, team_name, team_snapshot"


class PassesRepository:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    async def record(
        self, session_id: str, pass_no: int, team: Team, agents: list[Agent]
    ) -> None:
        await self._conn.execute(
            "INSERT OR REPLACE INTO session_passes"
            " (session_id, pass_no, team_id, team_name, team_snapshot)"
            " VALUES (?, ?, ?, ?, ?)",
            (session_id, pass_no, team.id, team.name, json.dumps(snapshot_of(team, agents))),
        )
        await self._conn.commit()

    async def _rows(self, session_id: str) -> list[dict]:
        async with self._conn.execute(
            f"SELECT {_COLUMNS} FROM session_passes WHERE session_id = ? ORDER BY pass_no",
            (session_id,),
        ) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

    async def team_for_pass(self, session: Session, pass_no: int) -> tuple[Team, list[Agent]]:
        """Who argued this pass: the nearest handover at or before it."""
        earlier = [row for row in await self._rows(session.id) if row["pass_no"] <= pass_no]
        return self._team(session, earlier)

    async def current_team(self, session: Session) -> tuple[Team, list[Agent]]:
        """Who holds the floor now, and so who argues the next pass."""
        return self._team(session, await self._rows(session.id))

    @staticmethod
    def _team(session: Session, rows: list[dict]) -> tuple[Team, list[Agent]]:
        if not rows:
            return team_from_session(session)
        return team_from_snapshot(json.loads(rows[-1]["team_snapshot"]))

    async def protocols(self, session: Session) -> dict[int, str]:
        """Sparse map of pass number to protocol, for the canvas."""
        protocols = {1: session.team_snapshot.get("team", {}).get("protocol", "relay")}
        for row in await self._rows(session.id):
            protocols[row["pass_no"]] = json.loads(row["team_snapshot"])["team"].get(
                "protocol", "relay"
            )
        return protocols

    async def timeline(self, session: Session) -> list[SessionPass]:
        """Every team that has held the floor, in order, for the header."""
        first = SessionPass(
            pass_no=1,
            team_id=session.team_id,
            team_name=session.team_name,
            protocol=session.team_snapshot.get("team", {}).get("protocol", "relay"),
        )
        handovers = [
            SessionPass(
                pass_no=row["pass_no"],
                team_id=row["team_id"],
                team_name=row["team_name"],
                protocol=json.loads(row["team_snapshot"])["team"].get("protocol", "relay"),
            )
            for row in await self._rows(session.id)
        ]
        return [first, *handovers]
