"""The model that writes the synthesis.

Left empty it is the first agent's, which is what the graph has always done.
Named on the team it is that one instead: a panel of small voices can hand its
tally to a model big enough to count reliably, without promoting one voter and
skewing the vote.
"""

import aiosqlite
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.db.agents import AgentsRepository
from src.db.schema import apply_schema
from src.db.teams import TeamsRepository
from src.graph.builder import build_graph, initial_state
from src.models import AgentCreate, TeamCreate, TeamUpdate
from tests.support import agent, make_deps, team


def _factory(calls: list[tuple[str, str]]):
    """Records the engine and model each node asks for."""

    def factory(provider: str, model: str, max_tokens: int | None = None):
        calls.append((provider, model))
        return FakeListChatModel(responses=["reply"])

    return factory


async def _run(the_team, agents) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []
    graph = build_graph(the_team, agents, make_deps(llm_factory=_factory(calls)))
    await graph.ainvoke(initial_state("s1", "an idea", 1))
    return calls


async def test_the_synthesis_borrows_the_first_agent_when_nothing_is_named():
    speaker = agent(1, "Advocate", 0, model="small")

    calls = await _run(team(), [speaker])

    assert calls[-1] == ("ollama", "small")


async def test_a_team_can_name_the_model_for_its_synthesis():
    speaker = agent(1, "Advocate", 0, model="small")

    calls = await _run(team(synthesis_model="big"), [speaker])

    assert calls[0] == ("ollama", "small")
    assert calls[-1] == ("ollama", "big")


async def test_the_synthesis_can_run_on_another_engine():
    speaker = agent(1, "Advocate", 0, model="small")

    calls = await _run(
        team(synthesis_provider="lmstudio", synthesis_model="big"), [speaker]
    )

    assert calls[-1] == ("lmstudio", "big")


async def test_naming_only_the_engine_keeps_the_first_agent_model():
    """Half an override is still an override of that half only."""
    speaker = agent(1, "Advocate", 0, model="small")

    calls = await _run(team(synthesis_provider="lmstudio"), [speaker])

    assert calls[-1] == ("lmstudio", "small")


async def test_a_team_stores_and_clears_the_fields(conn):
    repo = TeamsRepository(conn)

    created = await repo.create(
        TeamCreate(
            name="Panel",
            synthesis_prompt="count",
            synthesis_provider="lmstudio",
            synthesis_model="big",
        )
    )
    cleared = await repo.update(
        created.id, TeamUpdate(synthesis_provider=None, synthesis_model=None)
    )

    assert (created.synthesis_provider, created.synthesis_model) == ("lmstudio", "big")
    assert (cleared.synthesis_provider, cleared.synthesis_model) == (None, None)


async def test_a_team_stored_without_them_keeps_them_empty(conn):
    repo = TeamsRepository(conn)

    created = await repo.create(TeamCreate(name="Board", synthesis_prompt="x"))

    assert created.synthesis_provider is None
    assert created.synthesis_model is None


async def test_the_fields_survive_an_export_and_import(conn):
    from src.db.transfer import export_team, import_team

    teams = TeamsRepository(conn)
    created = await teams.create(
        TeamCreate(
            name="Panel",
            synthesis_prompt="count",
            synthesis_provider="lmstudio",
            synthesis_model="big",
        )
    )
    await AgentsRepository(conn).create(
        created.id, AgentCreate(name="Voice", system_prompt="vote", model="small")
    )

    imported = await import_team(conn, await export_team(conn, created.id))

    assert imported.synthesis_provider == "lmstudio"
    assert imported.synthesis_model == "big"


OLD_TEAMS = """
CREATE TABLE teams (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  name               TEXT    NOT NULL UNIQUE,
  description        TEXT,
  default_max_rounds INTEGER NOT NULL DEFAULT 2,
  synthesis_prompt   TEXT    NOT NULL,
  created_at         TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


async def test_the_columns_are_added_to_an_older_database():
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.executescript(OLD_TEAMS)

        await apply_schema(conn)

        async with conn.execute("PRAGMA table_info(teams)") as cursor:
            columns = {row[1] for row in await cursor.fetchall()}
        assert {"synthesis_provider", "synthesis_model"} <= columns


async def test_the_synthesis_model_is_checked_against_the_engines(client):
    """It has to fail before the debate, not two minutes into it."""
    created = (
        await client.post(
            "/api/v1/teams",
            json={
                "name": "Panel",
                "synthesis_prompt": "count",
                "synthesis_model": "not-installed",
            },
        )
    ).json()
    await client.post(
        f"/api/v1/teams/{created['id']}/agents",
        json={"name": "Voice", "system_prompt": "vote", "model": "m"},
    )

    response = await client.post(
        "/api/v1/sessions", json={"idea": "an idea", "team_id": created["id"]}
    )

    assert response.status_code == 422
    assert "not-installed" in response.json()["detail"]
