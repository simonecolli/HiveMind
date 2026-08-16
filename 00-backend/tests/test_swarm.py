"""Two protocols: a relay line and a swarm round."""

import aiosqlite

from src.db.schema import apply_schema
from src.db.teams import TeamsRepository
from src.db.transfer import export_team, import_team
from src.graph.builder import build_graph, initial_state
from src.models import TeamCreate, TeamUpdate
from tests.support import (
    InMemoryRecorder,
    RecordingEmitter,
    agent,
    make_deps,
    recording_llm_factory,
    team,
)

AGENTS = [agent(1, "Alfa", 0), agent(2, "Beta", 1)]


def _context_for(sink: list[list], who: str) -> str:
    """The human message handed to the agent whose system prompt names them."""
    for messages in sink:
        if who in str(messages[0].content):
            return str(messages[1].content)
    raise AssertionError(f"{who} never spoke")


async def _run(protocol: str, *, deps=None, max_rounds=1, agents=None):
    deps = deps or make_deps()
    graph = build_graph(team(protocol=protocol), agents or AGENTS, deps)
    return await graph.ainvoke(initial_state("s1", "an idea", max_rounds))


async def test_in_a_relay_the_second_agent_reads_the_first():
    sink: list[list] = []
    deps = make_deps(llm_factory=recording_llm_factory(sink, "spoke"))

    await _run("relay", deps=deps)

    assert "Alfa" in _context_for(sink, "you are Beta")


async def test_in_a_swarm_the_agents_of_a_round_do_not_read_each_other():
    """That is the point of the swarm: no anchoring on whoever went first."""
    sink: list[list] = []
    deps = make_deps(llm_factory=recording_llm_factory(sink, "spoke"))

    await _run("swarm", deps=deps)

    assert "Alfa" not in _context_for(sink, "you are Beta")


async def test_a_swarm_still_reads_the_previous_round():
    sink: list[list] = []
    deps = make_deps(llm_factory=recording_llm_factory(sink, "spoke"))

    await _run("swarm", deps=deps, max_rounds=2)

    # The last call belongs to round 2 or to the synthesis; either way the
    # first round has to be visible by then.
    assert any("round 1" in str(messages[1].content) for messages in sink)


async def test_every_agent_of_a_swarm_round_carries_the_same_round_number():
    state = await _run("swarm", max_rounds=2)

    rounds = [(t.agent_name, t.round) for t in state["turns"] if t.kind == "agent"]
    assert sorted(rounds) == [("Alfa", 1), ("Alfa", 2), ("Beta", 1), ("Beta", 2)]


async def test_a_swarm_hands_out_a_distinct_seq_to_each_parallel_turn():
    """Two agents in one superstep see the same state: counting turns in memory
    would give them the same number."""
    recorder = InMemoryRecorder()
    deps = make_deps(recorder=recorder)

    await _run("swarm", deps=deps, max_rounds=2)

    seqs = [r["seq"] for r in recorder.started]
    assert sorted(seqs) == list(range(len(seqs)))


async def test_the_canvas_never_loses_a_node_during_a_swarm_round():
    """Built per node from its own state, a parallel round would emit canvases
    missing the sibling that ran alongside."""
    emitter = RecordingEmitter()
    deps = make_deps(emitter=emitter)

    await _run("swarm", deps=deps, max_rounds=2)

    counts = [len(payload["nodes"]) for payload in emitter.payloads("graph")]
    assert counts == sorted(counts)
    assert counts[-1] == len(counts) + 1  # every turn, plus the idea


async def test_a_swarm_still_ends_with_the_synthesis():
    state = await _run("swarm", max_rounds=1)

    assert state["turns"][-1].kind == "synthesis"


async def test_a_team_remembers_its_protocol(conn):
    repo = TeamsRepository(conn)

    created = await repo.create(
        TeamCreate(name="Board", synthesis_prompt="x", protocol="swarm")
    )
    back = await repo.update(created.id, TeamUpdate(protocol="relay"))

    assert created.protocol == "swarm"
    assert back.protocol == "relay"


async def test_a_team_is_a_relay_unless_told_otherwise(conn):
    created = await TeamsRepository(conn).create(TeamCreate(name="Board", synthesis_prompt="x"))

    assert created.protocol == "relay"


async def test_the_protocol_survives_an_export_and_import(conn):
    repo = TeamsRepository(conn)
    t = await repo.create(TeamCreate(name="Board", synthesis_prompt="x", protocol="swarm"))

    imported = await import_team(conn, await export_team(conn, t.id))

    assert imported.protocol == "swarm"


OLD_TEAMS = """
CREATE TABLE teams (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, description TEXT,
  default_max_rounds INTEGER NOT NULL DEFAULT 2, synthesis_prompt TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


async def test_teams_written_before_the_swarm_stay_relays():
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.executescript(OLD_TEAMS)
        await conn.execute("INSERT INTO teams (name, synthesis_prompt) VALUES ('Board', 'x')")
        await conn.commit()

        await apply_schema(conn)

        assert (await TeamsRepository(conn).list())[0].protocol == "relay"
