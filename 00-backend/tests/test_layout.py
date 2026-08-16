from src.graph.layout import X_STEP, Y_STEP, build_canvas
from src.models import Turn


def _turn(**kwargs) -> Turn:
    base = dict(
        id=1,
        agent_id=1,
        agent_name="Advocate",
        agent_position=0,
        round=1,
        seq=0,
        kind="agent",
        title=None,
        text="text",
    )
    return Turn(**{**base, **kwargs})


def _node(canvas, node_id):
    return next(n for n in canvas.nodes if n.id == node_id)


def test_with_no_turns_only_the_idea_node_remains():
    canvas = build_canvas("a photographic installation", [])

    assert [n.id for n in canvas.nodes] == ["idea"]
    assert canvas.edges == []


def test_the_idea_node_carries_the_idea_text():
    canvas = build_canvas("a photographic installation", [])

    assert _node(canvas, "idea").data["label"] == "a photographic installation"


def test_the_node_id_is_the_turn_id():
    canvas = build_canvas("idea", [_turn(id=42)])

    assert [n.id for n in canvas.nodes] == ["idea", "42"]


def test_coordinates_come_from_round_and_agent_position():
    turns = [
        _turn(id=1, round=1, agent_position=0, seq=0),
        _turn(id=2, round=2, agent_position=1, seq=1),
    ]

    canvas = build_canvas("idea", turns)

    assert _node(canvas, "1").position == {"x": 0.0, "y": 0.0}
    assert _node(canvas, "2").position == {"x": float(X_STEP), "y": float(Y_STEP)}


def test_the_idea_precedes_the_first_turn():
    canvas = build_canvas("idea", [_turn(id=7)])

    assert [(e.source, e.target) for e in canvas.edges] == [("idea", "7")]


def test_turns_are_chained_in_sequence():
    turns = [_turn(id=1, seq=0), _turn(id=2, seq=1), _turn(id=3, seq=2)]

    canvas = build_canvas("idea", turns)

    assert [(e.source, e.target) for e in canvas.edges] == [
        ("idea", "1"),
        ("1", "2"),
        ("2", "3"),
    ]


def test_turns_are_ordered_by_seq_not_by_arrival():
    turns = [_turn(id=2, seq=1), _turn(id=1, seq=0)]

    canvas = build_canvas("idea", turns)

    assert [(e.source, e.target) for e in canvas.edges] == [("idea", "1"), ("1", "2")]


def test_the_label_includes_the_title_when_there_is_one():
    canvas = build_canvas("idea", [_turn(id=1, title="costs underestimated", round=2)])

    assert _node(canvas, "1").data["label"] == "Advocate - R2 - costs underestimated"


def test_without_a_title_the_label_is_agent_and_round():
    canvas = build_canvas("idea", [_turn(id=1, title=None, round=2)])

    assert _node(canvas, "1").data["label"] == "Advocate - R2"


def test_the_synthesis_sits_right_of_the_last_round():
    turns = [
        _turn(id=1, round=1, agent_position=0, seq=0),
        _turn(id=2, round=2, agent_position=0, seq=1),
        _turn(id=3, kind="synthesis", agent_name="Synthesis", round=2, seq=2),
    ]

    canvas = build_canvas("idea", turns)

    assert _node(canvas, "3").position["x"] == float(2 * X_STEP)


def test_the_synthesis_is_a_node_type_of_its_own():
    canvas = build_canvas("idea", [_turn(id=1, kind="synthesis", agent_name="Synthesis")])

    assert _node(canvas, "1").type == "synthesis"
    assert _node(canvas, "idea").type == "idea"
