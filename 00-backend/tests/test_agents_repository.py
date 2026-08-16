import pytest

from src.db.agents import AgentsRepository
from src.db.teams import TeamsRepository
from src.models import AgentCreate, AgentUpdate, TeamCreate


async def _team(conn, name: str = "Board") -> int:
    team = await TeamsRepository(conn).create(TeamCreate(name=name, synthesis_prompt="x"))
    return team.id


def _agent(name: str) -> AgentCreate:
    return AgentCreate(name=name, system_prompt=f"you are {name}", model="qwen2.5:7b")


async def test_create_assigns_incrementing_positions(conn):
    repo = AgentsRepository(conn)
    team_id = await _team(conn)

    first = await repo.create(team_id, _agent("Creative"))
    second = await repo.create(team_id, _agent("Advocate"))

    assert (first.position, second.position) == (0, 1)


async def test_positions_are_independent_per_team(conn):
    repo = AgentsRepository(conn)
    a = await _team(conn, "A")
    b = await _team(conn, "B")
    await repo.create(a, _agent("Creative"))

    first_of_b = await repo.create(b, _agent("Architect"))

    assert first_of_b.position == 0


async def test_list_by_team_is_sorted_by_position(conn):
    repo = AgentsRepository(conn)
    team_id = await _team(conn)
    creative = await repo.create(team_id, _agent("Creative"))
    advocate = await repo.create(team_id, _agent("Advocate"))

    await repo.reorder(team_id, [advocate.id, creative.id])

    assert [a.name for a in await repo.list_by_team(team_id)] == ["Advocate", "Creative"]


async def test_reorder_rewrites_positions_from_zero(conn):
    repo = AgentsRepository(conn)
    team_id = await _team(conn)
    a = await repo.create(team_id, _agent("A"))
    b = await repo.create(team_id, _agent("B"))
    c = await repo.create(team_id, _agent("C"))

    await repo.reorder(team_id, [c.id, a.id, b.id])

    assert [(x.name, x.position) for x in await repo.list_by_team(team_id)] == [
        ("C", 0),
        ("A", 1),
        ("B", 2),
    ]


async def test_reorder_rejects_incomplete_lists(conn):
    repo = AgentsRepository(conn)
    team_id = await _team(conn)
    a = await repo.create(team_id, _agent("A"))
    await repo.create(team_id, _agent("B"))

    with pytest.raises(ValueError, match="does not match"):
        await repo.reorder(team_id, [a.id])


async def test_reorder_rejects_agents_from_another_team(conn):
    repo = AgentsRepository(conn)
    team_id = await _team(conn, "A")
    other = await _team(conn, "B")
    mine = await repo.create(team_id, _agent("Mine"))
    stranger = await repo.create(other, _agent("Stranger"))

    with pytest.raises(ValueError, match="does not match"):
        await repo.reorder(team_id, [mine.id, stranger.id])


async def test_update_touches_only_the_fields_passed(conn):
    repo = AgentsRepository(conn)
    team_id = await _team(conn)
    agent = await repo.create(team_id, _agent("Advocate"))

    updated = await repo.update(agent.id, AgentUpdate(model="qwen2.5:14b"))

    assert updated.model == "qwen2.5:14b"
    assert updated.system_prompt == "you are Advocate"
    assert updated.position == agent.position


async def test_update_can_disable_an_agent(conn):
    repo = AgentsRepository(conn)
    team_id = await _team(conn)
    agent = await repo.create(team_id, _agent("Advocate"))

    updated = await repo.update(agent.id, AgentUpdate(enabled=False))

    assert updated.enabled is False


async def test_delete_preserves_the_order_of_the_rest(conn):
    repo = AgentsRepository(conn)
    team_id = await _team(conn)
    a = await repo.create(team_id, _agent("A"))
    b = await repo.create(team_id, _agent("B"))
    c = await repo.create(team_id, _agent("C"))

    await repo.delete(b.id)

    assert [x.id for x in await repo.list_by_team(team_id)] == [a.id, c.id]
