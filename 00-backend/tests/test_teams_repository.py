import pytest

from src.db.agents import AgentsRepository
from src.db.teams import TeamsRepository
from src.models import AgentCreate, TeamCreate, TeamUpdate


async def test_create_assigns_an_id_and_the_defaults(conn):
    repo = TeamsRepository(conn)

    team = await repo.create(TeamCreate(name="Board", synthesis_prompt="Sum up the debate."))

    assert team.id > 0
    assert team.name == "Board"
    assert team.default_max_rounds == 2


async def test_get_returns_the_created_team(conn):
    repo = TeamsRepository(conn)
    created = await repo.create(
        TeamCreate(name="Panel", synthesis_prompt="Synthesise.", default_max_rounds=5)
    )

    fetched = await repo.get(created.id)

    assert fetched == created


async def test_get_of_an_unknown_id_returns_none(conn):
    repo = TeamsRepository(conn)

    assert await repo.get(999) is None


async def test_duplicate_names_are_rejected(conn):
    repo = TeamsRepository(conn)
    await repo.create(TeamCreate(name="Board", synthesis_prompt="x"))

    with pytest.raises(ValueError, match="already exists"):
        await repo.create(TeamCreate(name="Board", synthesis_prompt="y"))


async def test_list_is_sorted_by_name(conn):
    repo = TeamsRepository(conn)
    await repo.create(TeamCreate(name="Zeta", synthesis_prompt="x"))
    await repo.create(TeamCreate(name="Alfa", synthesis_prompt="x"))

    teams = await repo.list()

    assert [t.name for t in teams] == ["Alfa", "Zeta"]


async def test_update_touches_only_the_fields_passed(conn):
    repo = TeamsRepository(conn)
    team = await repo.create(
        TeamCreate(name="Board", synthesis_prompt="original", default_max_rounds=3)
    )

    updated = await repo.update(team.id, TeamUpdate(name="Board revised"))

    assert updated.name == "Board revised"
    assert updated.synthesis_prompt == "original"
    assert updated.default_max_rounds == 3


async def test_delete_removes_the_team(conn):
    repo = TeamsRepository(conn)
    team = await repo.create(TeamCreate(name="Board", synthesis_prompt="x"))

    await repo.delete(team.id)

    assert await repo.get(team.id) is None


async def test_delete_cascades_to_the_agents(conn):
    teams = TeamsRepository(conn)
    agents = AgentsRepository(conn)
    team = await teams.create(TeamCreate(name="Board", synthesis_prompt="x"))
    await agents.create(
        team.id, AgentCreate(name="Advocate", system_prompt="push back", model="qwen2.5:7b")
    )

    await teams.delete(team.id)

    assert await agents.list_by_team(team.id) == []


async def test_duplicate_copies_team_and_agents_with_fresh_ids(conn):
    teams = TeamsRepository(conn)
    agents = AgentsRepository(conn)
    team = await teams.create(
        TeamCreate(name="Board", synthesis_prompt="synthesis", default_max_rounds=4)
    )
    original = await agents.create(
        team.id, AgentCreate(name="Advocate", system_prompt="push back", model="qwen2.5:7b")
    )

    copy = await teams.duplicate(team.id)

    assert copy.id != team.id
    assert copy.name == "Board (copy)"
    assert copy.default_max_rounds == 4
    assert copy.synthesis_prompt == "synthesis"

    copied_agents = await agents.list_by_team(copy.id)
    assert len(copied_agents) == 1
    assert copied_agents[0].id != original.id
    assert copied_agents[0].name == "Advocate"
    assert copied_agents[0].system_prompt == "push back"


async def test_duplicate_avoids_name_collisions(conn):
    repo = TeamsRepository(conn)
    team = await repo.create(TeamCreate(name="Board", synthesis_prompt="x"))
    await repo.duplicate(team.id)

    second = await repo.duplicate(team.id)

    assert second.name == "Board (copy 2)"
