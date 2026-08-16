import pytest

from src.db.agents import AgentsRepository
from src.db.teams import TeamsRepository
from src.db.transfer import export_team, import_team
from src.models import AgentCreate, TeamCreate, TeamExport


async def _seeded(conn, name: str = "Board") -> int:
    teams = TeamsRepository(conn)
    agents = AgentsRepository(conn)
    team = await teams.create(
        TeamCreate(
            name=name,
            description="the starting board",
            default_max_rounds=3,
            synthesis_prompt="Sum it up.",
        )
    )
    await agents.create(
        team.id, AgentCreate(name="Creative", system_prompt="expand", model="qwen2.5:7b")
    )
    await agents.create(
        team.id,
        AgentCreate(name="Advocate", system_prompt="push back", model="qwen2.5:14b", enabled=False),
    )
    return team.id


async def test_export_carries_the_team_settings(conn):
    team_id = await _seeded(conn)

    payload = await export_team(conn, team_id)

    assert payload.name == "Board"
    assert payload.description == "the starting board"
    assert payload.default_max_rounds == 3
    assert payload.synthesis_prompt == "Sum it up."


async def test_export_keeps_agents_in_speaking_order(conn):
    team_id = await _seeded(conn)

    payload = await export_team(conn, team_id)

    assert [a.name for a in payload.agents] == ["Creative", "Advocate"]


async def test_export_carries_model_and_enabled_flag(conn):
    team_id = await _seeded(conn)

    payload = await export_team(conn, team_id)

    assert [(a.model, a.enabled) for a in payload.agents] == [
        ("qwen2.5:7b", True),
        ("qwen2.5:14b", False),
    ]


async def test_export_omits_ids_and_timestamps(conn):
    """Ids mean nothing on another machine, so they must not travel."""
    team_id = await _seeded(conn)

    dumped = (await export_team(conn, team_id)).model_dump()

    assert "id" not in dumped
    assert "created_at" not in dumped
    assert all("id" not in agent for agent in dumped["agents"])


async def test_export_of_an_unknown_team_is_none(conn):
    assert await export_team(conn, 999) is None


async def test_import_creates_the_team_and_its_agents(conn):
    payload = TeamExport(
        name="Imported",
        synthesis_prompt="Sum it up.",
        agents=[{"name": "Creative", "system_prompt": "expand", "model": "m"}],
    )

    team = await import_team(conn, payload)

    assert team.name == "Imported"
    agents = await AgentsRepository(conn).list_by_team(team.id)
    assert [a.name for a in agents] == ["Creative"]


async def test_import_preserves_order_and_the_enabled_flag(conn):
    payload = TeamExport(
        name="Imported",
        synthesis_prompt="x",
        agents=[
            {"name": "First", "system_prompt": "a", "model": "m"},
            {"name": "Second", "system_prompt": "b", "model": "m", "enabled": False},
        ],
    )

    team = await import_team(conn, payload)

    agents = await AgentsRepository(conn).list_by_team(team.id)
    assert [(a.name, a.position, a.enabled) for a in agents] == [
        ("First", 0, True),
        ("Second", 1, False),
    ]


async def test_import_renames_when_the_name_is_taken(conn):
    await _seeded(conn, "Board")
    payload = TeamExport(name="Board", synthesis_prompt="x", agents=[])

    team = await import_team(conn, payload)

    assert team.name == "Board (copy)"


async def test_import_keeps_the_name_when_it_is_free(conn):
    payload = TeamExport(name="Board", synthesis_prompt="x", agents=[])

    team = await import_team(conn, payload)

    assert team.name == "Board"


async def test_import_accepts_a_team_with_no_agents(conn):
    payload = TeamExport(name="Empty", synthesis_prompt="x", agents=[])

    team = await import_team(conn, payload)

    assert await AgentsRepository(conn).list_by_team(team.id) == []


async def test_a_round_trip_reproduces_the_team(conn):
    team_id = await _seeded(conn)
    exported = await export_team(conn, team_id)

    imported = await import_team(conn, exported)

    reexported = await export_team(conn, imported.id)
    assert reexported.model_dump(exclude={"name"}) == exported.model_dump(exclude={"name"})


async def test_a_failed_import_leaves_no_half_built_team(conn, monkeypatch):
    """The compensating delete is what keeps a broken file from littering the list."""
    payload = TeamExport(
        name="Imported",
        synthesis_prompt="x",
        agents=[
            {"name": "First", "system_prompt": "a", "model": "m"},
            {"name": "Second", "system_prompt": "b", "model": "m"},
        ],
    )

    calls = {"n": 0}
    original = AgentsRepository.create

    async def explode_on_second(self, team_id, data):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("disk on fire")
        return await original(self, team_id, data)

    monkeypatch.setattr(AgentsRepository, "create", explode_on_second)

    with pytest.raises(RuntimeError):
        await import_team(conn, payload)

    assert await TeamsRepository(conn).list() == []
