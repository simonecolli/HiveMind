"""Each agent names the engine it wants, and the session refuses to start blind."""

import aiosqlite

from src.db.agents import AgentsRepository
from src.db.schema import apply_schema
from src.db.teams import TeamsRepository
from src.db.transfer import export_team, import_team
from src.models import AgentCreate, AgentUpdate, TeamCreate
from tests.support import StubEngines

OLLAMA_ONLY = [
    {"provider": "ollama", "label": "Ollama", "available": True, "models": ["m"]},
    {"provider": "lmstudio", "label": "LM Studio", "available": False, "models": []},
]
BOTH_UP = [
    {"provider": "ollama", "label": "Ollama", "available": True, "models": ["m"]},
    {
        "provider": "lmstudio",
        "label": "LM Studio",
        "available": True,
        "models": ["google/gemma-4-e4b"],
    },
]


async def _team_with(client, *agents: dict) -> dict:
    team = (
        await client.post("/api/v1/teams", json={"name": "Board", "synthesis_prompt": "x"})
    ).json()
    for agent in agents:
        await client.post(f"/api/v1/teams/{team['id']}/agents", json=agent)
    return team


async def test_an_agent_defaults_to_ollama(conn):
    teams = TeamsRepository(conn)
    repo = AgentsRepository(conn)
    t = await teams.create(TeamCreate(name="Board", synthesis_prompt="x"))

    created = await repo.create(t.id, AgentCreate(name="A", system_prompt="p", model="m"))

    assert created.provider == "ollama"


async def test_an_agent_can_be_put_on_lm_studio(conn):
    teams = TeamsRepository(conn)
    repo = AgentsRepository(conn)
    t = await teams.create(TeamCreate(name="Board", synthesis_prompt="x"))

    created = await repo.create(
        t.id,
        AgentCreate(name="A", system_prompt="p", model="google/gemma-4-e4b", provider="lmstudio"),
    )
    moved_back = await repo.update(created.id, AgentUpdate(provider="ollama"))

    assert created.provider == "lmstudio"
    assert moved_back.provider == "ollama"


async def test_the_engine_survives_an_export_and_import(conn):
    teams = TeamsRepository(conn)
    agents = AgentsRepository(conn)
    t = await teams.create(TeamCreate(name="Board", synthesis_prompt="x"))
    await agents.create(
        t.id, AgentCreate(name="A", system_prompt="p", model="gemma", provider="lmstudio")
    )

    imported = await import_team(conn, await export_team(conn, t.id))

    assert (await agents.list_by_team(imported.id))[0].provider == "lmstudio"


async def test_the_models_route_returns_a_catalogue_per_engine(client, app_deps):
    app_deps.engines = StubEngines(BOTH_UP)

    catalogue = (await client.get("/api/v1/models")).json()

    assert [c["provider"] for c in catalogue] == ["ollama", "lmstudio"]
    assert catalogue[1]["models"] == ["google/gemma-4-e4b"]


async def test_a_session_starts_when_every_agent_has_its_model(client, app_deps):
    app_deps.engines = StubEngines(BOTH_UP)
    team = await _team_with(
        client,
        {"name": "A", "system_prompt": "p", "model": "m"},
        {
            "name": "B",
            "system_prompt": "p",
            "model": "google/gemma-4-e4b",
            "provider": "lmstudio",
        },
    )

    response = await client.post("/api/v1/sessions", json={"idea": "x", "team_id": team["id"]})

    assert response.status_code == 201


async def test_a_missing_model_is_refused_by_name(client, app_deps):
    """The failure has to name the agent: with two engines this is the everyday
    mistake, not an exotic one."""
    app_deps.engines = StubEngines(BOTH_UP)
    team = await _team_with(
        client, {"name": "Advocate", "system_prompt": "p", "model": "not-installed"}
    )

    response = await client.post("/api/v1/sessions", json={"idea": "x", "team_id": team["id"]})

    assert response.status_code == 422
    assert "Advocate" in response.json()["detail"]
    assert "not-installed" in response.json()["detail"]


async def test_an_agent_on_a_stopped_engine_gives_503(client, app_deps):
    app_deps.engines = StubEngines(OLLAMA_ONLY)
    team = await _team_with(
        client,
        {"name": "B", "system_prompt": "p", "model": "gemma", "provider": "lmstudio"},
    )

    response = await client.post("/api/v1/sessions", json={"idea": "x", "team_id": team["id"]})

    assert response.status_code == 503
    assert "LM Studio" in response.json()["detail"]


async def test_a_stopped_engine_nobody_uses_does_not_block_the_debate(client, app_deps):
    app_deps.engines = StubEngines(OLLAMA_ONLY)
    team = await _team_with(client, {"name": "A", "system_prompt": "p", "model": "m"})

    response = await client.post("/api/v1/sessions", json={"idea": "x", "team_id": team["id"]})

    assert response.status_code == 201


OLD_AGENTS = """
CREATE TABLE teams (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, description TEXT,
  default_max_rounds INTEGER NOT NULL DEFAULT 2, synthesis_prompt TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE agents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  name TEXT NOT NULL, system_prompt TEXT NOT NULL, model TEXT NOT NULL,
  position INTEGER NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


async def test_agents_written_before_lm_studio_stay_on_ollama():
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.executescript(OLD_AGENTS)
        await conn.execute(
            "INSERT INTO teams (name, synthesis_prompt) VALUES ('Board', 'x')"
        )
        await conn.execute(
            "INSERT INTO agents (team_id, name, system_prompt, model, position)"
            " VALUES (1, 'A', 'p', 'm', 0)"
        )
        await conn.commit()

        await apply_schema(conn)

        assert (await AgentsRepository(conn).list_by_team(1))[0].provider == "ollama"
