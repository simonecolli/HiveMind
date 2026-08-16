"""Rebuilding a team from the copy frozen into a session.

A follow-up runs on the snapshot rather than on the live team, so editing a
prompt or deleting the team midway cannot change who is arguing. A session that
hands over to another team freezes that one too, on the same terms.
"""

from src.models import Agent, Session, Team


def snapshot_of(team: Team, agents: list[Agent]) -> dict:
    return {"team": team.model_dump(), "agents": [agent.model_dump() for agent in agents]}


def team_from_snapshot(snapshot: dict) -> tuple[Team, list[Agent]]:
    return (
        Team(**snapshot["team"]),
        [Agent(**agent) for agent in snapshot["agents"]],
    )


def team_from_session(session: Session) -> tuple[Team, list[Agent]]:
    """The team the session opened with, before any handover."""
    return team_from_snapshot(session.team_snapshot)
