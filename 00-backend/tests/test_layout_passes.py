"""Layout across several passes of the same session."""

from src.graph.layout import X_STEP, build_canvas
from src.models import Turn


def _turn(**kwargs) -> Turn:
    base = dict(
        id=1,
        agent_id=1,
        agent_name="Advocate",
        agent_position=0,
        pass_no=1,
        round=1,
        seq=0,
        kind="agent",
        title=None,
        text="text",
    )
    return Turn(**{**base, **kwargs})


def _x(canvas, node_id: str) -> float:
    return next(n for n in canvas.nodes if n.id == node_id).position["x"]


def _columns(canvas) -> list[tuple[str, float]]:
    return [(n.id, n.position["x"]) for n in canvas.nodes]


def test_a_single_pass_is_unchanged():
    turns = [
        _turn(id=1, round=1, seq=0),
        _turn(id=2, round=2, seq=1),
        _turn(id=3, kind="synthesis", agent_name="Synthesis", round=2, seq=2),
    ]

    canvas = build_canvas("idea", turns)

    assert _x(canvas, "1") == 0.0
    assert _x(canvas, "2") == float(X_STEP)
    assert _x(canvas, "3") == float(2 * X_STEP)


def test_the_follow_up_message_gets_its_own_column():
    turns = [
        _turn(id=1, round=1, seq=0),
        _turn(id=2, kind="synthesis", agent_name="Synthesis", round=1, seq=1),
        _turn(id=3, kind="message", agent_name="You", pass_no=2, round=0, seq=2),
    ]

    canvas = build_canvas("idea", turns)

    assert _x(canvas, "3") == float(2 * X_STEP)


def test_the_second_pass_continues_to_the_right_of_the_first():
    turns = [
        _turn(id=1, round=1, seq=0),
        _turn(id=2, kind="synthesis", agent_name="Synthesis", round=1, seq=1),
        _turn(id=3, kind="message", agent_name="You", pass_no=2, round=0, seq=2),
        _turn(id=4, pass_no=2, round=1, seq=3),
        _turn(id=5, kind="synthesis", agent_name="Synthesis", pass_no=2, round=1, seq=4),
    ]

    canvas = build_canvas("idea", turns)

    assert [x for _, x in _columns(canvas)] == [
        float(-X_STEP),  # idea
        0.0,  # pass 1, round 1
        float(X_STEP),  # pass 1, synthesis
        float(2 * X_STEP),  # message
        float(3 * X_STEP),  # pass 2, round 1
        float(4 * X_STEP),  # pass 2, synthesis
    ]


def test_rounds_of_the_same_pass_share_no_column_with_another_pass():
    """Round 1 of pass 2 must not land on top of round 1 of pass 1."""
    turns = [
        _turn(id=1, pass_no=1, round=1, seq=0),
        _turn(id=2, kind="synthesis", pass_no=1, round=1, seq=1),
        _turn(id=3, kind="message", pass_no=2, round=0, seq=2),
        _turn(id=4, pass_no=2, round=1, seq=3),
    ]

    canvas = build_canvas("idea", turns)

    assert _x(canvas, "4") != _x(canvas, "1")


def test_a_pass_with_more_rounds_takes_more_columns():
    turns = [
        _turn(id=1, pass_no=1, round=1, seq=0),
        _turn(id=2, kind="synthesis", pass_no=1, round=1, seq=1),
        _turn(id=3, kind="message", pass_no=2, round=0, seq=2),
        _turn(id=4, pass_no=2, round=1, seq=3),
        _turn(id=5, pass_no=2, round=2, seq=4),
        _turn(id=6, kind="synthesis", pass_no=2, round=2, seq=5),
    ]

    canvas = build_canvas("idea", turns)

    # round 1 | synthesis 1 | message | round 1 | round 2 | synthesis 2
    assert _x(canvas, "6") == float(5 * X_STEP)


def test_the_message_node_has_its_own_type():
    turns = [_turn(id=1, kind="message", agent_name="You", pass_no=2, round=0, seq=0)]

    canvas = build_canvas("idea", turns)

    node = next(n for n in canvas.nodes if n.id == "1")
    assert node.type == "message"


def test_the_message_label_is_its_text_not_the_agent_name():
    turns = [
        _turn(
            id=1,
            kind="message",
            agent_name="You",
            pass_no=2,
            round=0,
            seq=0,
            text="and if we did it outdoors?",
        )
    ]

    canvas = build_canvas("idea", turns)

    node = next(n for n in canvas.nodes if n.id == "1")
    assert node.data["label"] == "and if we did it outdoors?"


def test_the_chain_still_follows_seq_across_passes():
    turns = [
        _turn(id=1, pass_no=1, round=1, seq=0),
        _turn(id=2, kind="synthesis", pass_no=1, round=1, seq=1),
        _turn(id=3, kind="message", pass_no=2, round=0, seq=2),
        _turn(id=4, pass_no=2, round=1, seq=3),
    ]

    canvas = build_canvas("idea", turns)

    assert [(e.source, e.target) for e in canvas.edges] == [
        ("idea", "1"),
        ("1", "2"),
        ("2", "3"),
        ("3", "4"),
    ]
