import pytest

from src.graph.builder import build_graph, initial_state
from tests.support import (
    InMemoryRecorder,
    RecordingEmitter,
    agent,
    echo_llm_factory,
    failing_titler,
    make_deps,
    team,
)


async def _run(agents, *, max_rounds=1, deps=None, idea="an idea"):
    deps = deps or make_deps()
    graph = build_graph(team(), agents, deps)
    state = await graph.ainvoke(initial_state("s1", idea, max_rounds))
    return state, deps


async def test_one_round_runs_each_agent_once():
    agents = [agent(1, "Creative", 0), agent(2, "Advocate", 1)]

    state, _ = await _run(agents, max_rounds=1)

    speakers = [t.agent_name for t in state["turns"] if t.kind == "agent"]
    assert speakers == ["Creative", "Advocate"]


async def test_agents_speak_in_position_order():
    agents = [agent(2, "Advocate", 1), agent(1, "Creative", 0)]

    state, _ = await _run(agents, max_rounds=1)

    assert [t.agent_name for t in state["turns"] if t.kind == "agent"] == [
        "Creative",
        "Advocate",
    ]


async def test_two_rounds_double_the_turns():
    agents = [agent(1, "Creative", 0), agent(2, "Advocate", 1)]

    state, _ = await _run(agents, max_rounds=2)

    assert [(t.agent_name, t.round) for t in state["turns"] if t.kind == "agent"] == [
        ("Creative", 1),
        ("Advocate", 1),
        ("Creative", 2),
        ("Advocate", 2),
    ]


async def test_disabled_agents_stay_silent():
    agents = [agent(1, "Creative", 0), agent(2, "Mute", 1, enabled=False)]

    state, _ = await _run(agents, max_rounds=1)

    assert "Mute" not in [t.agent_name for t in state["turns"]]


async def test_the_synthesis_closes_the_debate():
    state, _ = await _run([agent(1, "Creative", 0)], max_rounds=2)

    last = state["turns"][-1]
    assert last.kind == "synthesis"
    assert last.agent_name == "Synthesis"


async def test_seq_increments_across_every_turn():
    agents = [agent(1, "Creative", 0), agent(2, "Advocate", 1)]

    state, _ = await _run(agents, max_rounds=2)

    assert [t.seq for t in state["turns"]] == list(range(len(state["turns"])))


async def test_each_agent_uses_its_own_model():
    agents = [agent(1, "Creative", 0, model="qwen2.5:14b"), agent(2, "Advocate", 1, model="qwen2.5:7b")]
    deps = make_deps(
        llm_factory=echo_llm_factory({"qwen2.5:14b": "vision", "qwen2.5:7b": "objection"})
    )

    state, _ = await _run(agents, max_rounds=1, deps=deps)

    texts = [t.text for t in state["turns"] if t.kind == "agent"]
    assert texts == ["vision", "objection"]


async def test_a_team_with_no_enabled_agents_is_rejected():
    with pytest.raises(ValueError, match="no enabled agents"):
        build_graph(team(), [agent(1, "Mute", 0, enabled=False)], make_deps())


async def test_the_turn_carries_the_generated_title():
    state, _ = await _run([agent(1, "Creative", 0)], max_rounds=1)

    assert state["turns"][0].title == "title"


async def test_a_missing_title_does_not_stop_the_debate():
    deps = make_deps(titler=failing_titler)

    state, _ = await _run([agent(1, "Creative", 0)], max_rounds=1, deps=deps)

    assert state["turns"][0].title is None
    assert state["turns"][-1].kind == "synthesis"


async def test_every_turn_is_persisted_by_the_recorder():
    recorder = InMemoryRecorder()
    deps = make_deps(recorder=recorder)

    state, _ = await _run([agent(1, "Creative", 0)], max_rounds=1, deps=deps)

    assert len(recorder.started) == len(state["turns"])
    assert [f["id"] for f in recorder.finished] == [t.id for t in state["turns"]]


async def test_events_arrive_in_the_expected_order():
    emitter = RecordingEmitter()
    deps = make_deps(emitter=emitter)

    await _run([agent(1, "Creative", 0)], max_rounds=1, deps=deps)

    names = emitter.names()
    assert names[0] == "turn.start"
    assert "turn.delta" in names
    assert names.index("turn.end") < names.index("graph")
    assert names[-1] == "graph"


async def test_the_deltas_reassemble_the_turn_text():
    emitter = RecordingEmitter()
    deps = make_deps(
        llm_factory=echo_llm_factory({"m": "hello"}), emitter=emitter
    )

    await _run([agent(1, "Creative", 0)], max_rounds=1, deps=deps)

    first_turn = emitter.payloads("turn.start")[0]["turn_id"]
    deltas = [
        d["text"] for d in emitter.payloads("turn.delta") if d["turn_id"] == first_turn
    ]
    assert "".join(deltas) == "hello"


async def test_the_graph_event_carries_the_updated_canvas():
    emitter = RecordingEmitter()
    deps = make_deps(emitter=emitter)

    await _run([agent(1, "Creative", 0)], max_rounds=1, deps=deps, idea="installation")

    latest_canvas = emitter.payloads("graph")[-1]
    assert latest_canvas["nodes"][0]["data"]["label"] == "installation"
    assert len(latest_canvas["nodes"]) == 3  # idea + agent + synthesis
