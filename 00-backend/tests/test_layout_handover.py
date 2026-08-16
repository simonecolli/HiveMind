"""A session whose passes did not all run under the same protocol.

Handing a session over to another team means the canvas can no longer assume
one wiring for the whole strip: a swarm panel can be followed by a relay desk,
and each half has to be drawn the way it actually ran.
"""

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


# A swarm pass of two agents, then a relay pass of two agents behind a message.
SWARM_THEN_RELAY = [
    _turn(id=1, agent_position=0, pass_no=1, round=1, seq=0),
    _turn(id=2, agent_position=1, pass_no=1, round=1, seq=1),
    _turn(id=3, kind="synthesis", agent_name="Synthesis", pass_no=1, round=1, seq=2),
    _turn(id=4, kind="message", agent_name="You", pass_no=2, round=0, seq=3),
    _turn(id=5, agent_position=0, pass_no=2, round=1, seq=4),
    _turn(id=6, agent_position=1, pass_no=2, round=1, seq=5),
]


def test_each_pass_is_wired_with_its_own_protocol():
    canvas = build_canvas("idea", SWARM_THEN_RELAY, {1: "swarm", 2: "relay"})

    pairs = _pairs(canvas)
    # The swarm half fans.
    assert ("idea", "1") in pairs and ("idea", "2") in pairs
    assert ("1", "2") not in pairs
    # The relay half is a thread.
    assert ("4", "5") in pairs and ("5", "6") in pairs


def test_the_handover_is_joined_across_the_pass_boundary():
    """The strip stays one strip: pass 2 hangs off the end of pass 1."""
    canvas = build_canvas("idea", SWARM_THEN_RELAY, {1: "swarm", 2: "relay"})

    assert ("3", "4") in _pairs(canvas)


def test_a_relay_pass_after_a_swarm_pass_starts_from_the_whole_last_layer():
    turns = [
        _turn(id=1, agent_position=0, pass_no=1, round=1, seq=0),
        _turn(id=2, agent_position=1, pass_no=1, round=1, seq=1),
        _turn(id=3, kind="message", agent_name="You", pass_no=2, round=0, seq=2),
    ]

    canvas = build_canvas("idea", turns, {1: "swarm", 2: "relay"})

    assert ("1", "3") in _pairs(canvas)
    assert ("2", "3") in _pairs(canvas)


def test_a_pass_with_no_entry_keeps_the_protocol_of_the_pass_before():
    """The mapping records handovers only, so an unnamed pass has not changed."""
    turns = SWARM_THEN_RELAY + [
        _turn(id=7, kind="message", agent_name="You", pass_no=3, round=0, seq=6),
        _turn(id=8, agent_position=0, pass_no=3, round=1, seq=7),
        _turn(id=9, agent_position=1, pass_no=3, round=1, seq=8),
    ]

    canvas = build_canvas("idea", turns, {1: "swarm", 2: "relay"})

    assert ("7", "8") in _pairs(canvas)
    assert ("8", "9") in _pairs(canvas)


def test_a_bare_string_still_applies_to_every_pass():
    """The old signature keeps working for sessions that never handed over."""
    by_string = _pairs(build_canvas("idea", SWARM_THEN_RELAY, "swarm"))
    by_mapping = _pairs(build_canvas("idea", SWARM_THEN_RELAY, {1: "swarm"}))

    assert by_string == by_mapping
