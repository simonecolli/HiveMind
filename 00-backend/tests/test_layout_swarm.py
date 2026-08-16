"""The canvas has to draw what actually happened, and that differs per protocol."""

from src.graph.layout import build_canvas
from src.models import Turn


def _turn(**kwargs) -> Turn:
    base = dict(
        id=1,
        agent_id=1,
        agent_name="A",
        agent_position=0,
        pass_no=1,
        round=1,
        seq=0,
        kind="agent",
        title=None,
        text="text",
    )
    return Turn(**{**base, **kwargs})


def _pairs(canvas) -> set[tuple[str, str]]:
    return {(e.source, e.target) for e in canvas.edges}


ROUND_OF_THREE = [
    _turn(id=1, agent_name="A", agent_position=0, round=1, seq=0),
    _turn(id=2, agent_name="B", agent_position=1, round=1, seq=1),
    _turn(id=3, agent_name="C", agent_position=2, round=1, seq=2),
]


def test_a_relay_keeps_the_single_thread():
    canvas = build_canvas("idea", ROUND_OF_THREE, protocol="relay")

    assert _pairs(canvas) == {("idea", "1"), ("1", "2"), ("2", "3")}


def test_the_default_is_still_the_relay_thread():
    assert _pairs(build_canvas("idea", ROUND_OF_THREE)) == {("idea", "1"), ("1", "2"), ("2", "3")}


def test_a_swarm_round_fans_out_of_the_idea():
    canvas = build_canvas("idea", ROUND_OF_THREE, protocol="swarm")

    assert _pairs(canvas) == {("idea", "1"), ("idea", "2"), ("idea", "3")}


def test_a_swarm_never_draws_agents_of_one_round_talking_to_each_other():
    """They ran in the same superstep: none of them read the others."""
    canvas = build_canvas("idea", ROUND_OF_THREE, protocol="swarm")

    assert ("1", "2") not in _pairs(canvas)
    assert ("2", "3") not in _pairs(canvas)


def test_a_swarm_joins_every_agent_of_a_round_to_every_agent_of_the_next():
    turns = ROUND_OF_THREE + [
        _turn(id=4, agent_name="A", agent_position=0, round=2, seq=3),
        _turn(id=5, agent_name="B", agent_position=1, round=2, seq=4),
    ]

    canvas = build_canvas("idea", turns, protocol="swarm")

    for source in ("1", "2", "3"):
        for target in ("4", "5"):
            assert (source, target) in _pairs(canvas)


def test_a_swarm_gathers_the_last_round_into_the_synthesis():
    turns = ROUND_OF_THREE + [
        _turn(id=9, kind="synthesis", agent_name="Synthesis", agent_position=3, seq=3)
    ]

    canvas = build_canvas("idea", turns, protocol="swarm")

    assert {("1", "9"), ("2", "9"), ("3", "9")} <= _pairs(canvas)


def test_a_follow_up_message_reopens_the_fan():
    turns = [
        _turn(id=1, round=1, seq=0),
        _turn(id=2, kind="synthesis", agent_name="Synthesis", round=1, seq=1),
        _turn(id=3, kind="message", agent_name="You", pass_no=2, round=0, seq=2),
        _turn(id=4, agent_name="A", agent_position=0, pass_no=2, round=1, seq=3),
        _turn(id=5, agent_name="B", agent_position=1, pass_no=2, round=1, seq=4),
    ]

    canvas = build_canvas("idea", turns, protocol="swarm")

    assert {("3", "4"), ("3", "5")} <= _pairs(canvas)
    assert ("4", "5") not in _pairs(canvas)


def test_the_nodes_are_the_same_whatever_the_protocol():
    """Only the wiring differs: a round is one column in both."""
    relay = build_canvas("idea", ROUND_OF_THREE, protocol="relay")
    swarm = build_canvas("idea", ROUND_OF_THREE, protocol="swarm")

    assert [(n.id, n.position) for n in relay.nodes] == [
        (n.id, n.position) for n in swarm.nodes
    ]
