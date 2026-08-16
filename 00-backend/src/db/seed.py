"""Default team: the board of directors described in the README."""

import aiosqlite

from src.db.agents import AgentsRepository
from src.db.teams import TeamsRepository
from src.models import AgentCreate, TeamCreate

DEFAULT_MODEL = "qwen2.5:7b"

DEFAULT_TEAM = TeamCreate(
    name="Board of Directors",
    description="The starting board: vision, objections, feasibility.",
    default_max_rounds=2,
    synthesis_prompt=(
        "You are the secretary of the board. Condense the debate into an"
        " orderly summary: the direction that emerged, the objections still"
        " open, and the concrete next steps. Write in prose, no bullet lists."
    ),
)

DEFAULT_AGENTS = [
    AgentCreate(
        name="Creative Director",
        model=DEFAULT_MODEL,
        max_output_length_in_words=200,
        system_prompt=(
            "You are the Creative Director. Expand the idea on vision,"
            " aesthetic impact and visual storytelling. Propose concrete"
            " directions, not generic praise."
        ),
    ),
    AgentCreate(
        name="Devil's Advocate",
        model=DEFAULT_MODEL,
        max_output_length_in_words=200,
        system_prompt=(
            "You are the devil's advocate. Find the weak points without mercy:"
            " cost, timelines, technical constraints, privacy issues, execution"
            " risk. No diplomacy, but argue every objection."
        ),
    ),
    AgentCreate(
        name="Software Architect",
        model=DEFAULT_MODEL,
        max_output_length_in_words=200,
        system_prompt=(
            "You are the software architect. Propose the stack and the"
            " architecture that answer the objections raised, naming the"
            " trade-offs. Concrete and verifiable."
        ),
    ),
]


async def seed_default_team(conn: aiosqlite.Connection) -> None:
    """Idempotent: if a team already exists, it touches nothing."""
    teams = TeamsRepository(conn)
    if await teams.list():
        return

    team = await teams.create(DEFAULT_TEAM)
    agents = AgentsRepository(conn)
    for agent in DEFAULT_AGENTS:
        await agents.create(team.id, agent)
