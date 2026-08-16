"""From the list of turns to the React Flow canvas.

No LLM produces topology: nodes, edges and coordinates are a deterministic
function of the turns, so the canvas is recomputed rather than persisted.
"""

from src.models import Canvas, CanvasEdge, CanvasNode, Turn

X_STEP = 320
Y_STEP = 180

IDEA_NODE_ID = "idea"


def build_canvas(
    idea: str, turns: list[Turn], protocol: str | dict[int, str] = "relay"
) -> Canvas:
    """The canvas for a session.

    `protocol` is either one protocol for the whole session, or a mapping from
    pass number to protocol. The mapping is sparse on purpose: it records the
    passes that changed team, and a pass with no entry of its own carries on
    with the protocol of the pass before it.
    """
    ordered = sorted(turns, key=lambda t: t.seq)
    columns = _columns(ordered)

    nodes = [
        CanvasNode(
            id=IDEA_NODE_ID,
            type="idea",
            position={"x": float(-X_STEP), "y": 0.0},
            data={"label": idea},
        )
    ]
    nodes.extend(_turn_node(turn, columns[_column_key(turn)]) for turn in ordered)

    return Canvas(nodes=nodes, edges=_edges(ordered, columns, protocol))


def _edges(
    ordered: list[Turn], columns: dict[tuple, int], protocol: str | dict[int, str]
) -> list[CanvasEdge]:
    """Wire one pass at a time, joining each to the tail of the one before.

    Passes are contiguous in `seq`, so wiring them separately and threading the
    joins reproduces exactly what a single protocol used to draw - while letting
    a session that handed over draw each half the way it ran.
    """
    edges: list[CanvasEdge] = []
    previous = [IDEA_NODE_ID]
    for pass_no, turns in _by_pass(ordered):
        wire = _swarm_pass if _protocol_for(pass_no, protocol) == "swarm" else _relay_pass
        pass_edges, previous = wire(turns, columns, previous)
        edges.extend(pass_edges)
    return edges


def _protocol_for(pass_no: int, protocol: str | dict[int, str]) -> str:
    if isinstance(protocol, str):
        return protocol
    # Forward-filled: the nearest entry at or before this pass still holds.
    earlier = [known for known in protocol if known <= pass_no]
    return protocol[max(earlier)] if earlier else "relay"


def _by_pass(ordered: list[Turn]) -> list[tuple[int, list[Turn]]]:
    grouped: dict[int, list[Turn]] = {}
    for turn in ordered:
        grouped.setdefault(turn.pass_no, []).append(turn)
    return sorted(grouped.items())


def _edge(source: str, target: str) -> CanvasEdge:
    return CanvasEdge(id=f"e-{source}-{target}", source=source, target=target)


def _relay_pass(
    turns: list[Turn], _columns_by_key: dict, previous: list[str]
) -> tuple[list[CanvasEdge], list[str]]:
    """One thread: each turn hands over to the next, which is what happened."""
    ids = [str(turn.id) for turn in turns]
    edges = [_edge(source, ids[0]) for source in previous]
    edges += [_edge(source, target) for source, target in zip(ids, ids[1:])]
    return edges, [ids[-1]]


def _swarm_pass(
    turns: list[Turn], columns_by_key: dict, previous: list[str]
) -> tuple[list[CanvasEdge], list[str]]:
    """Every node of a layer feeds every node of the next.

    A swarm round runs in one superstep, so its agents never read each other -
    drawing a thread between them would be a lie. What they do read is the whole
    previous round, which is exactly this mesh.
    """
    layers: dict[int, list[str]] = {}
    for turn in turns:
        layers.setdefault(columns_by_key[_column_key(turn)], []).append(str(turn.id))

    edges: list[CanvasEdge] = []
    for column in sorted(layers):
        current = layers[column]
        edges.extend(_edge(source, target) for source in previous for target in current)
        previous = current
    return edges, previous


def _columns(ordered: list[Turn]) -> dict[tuple, int]:
    """One column per group, numbered in the order the groups first appear.

    Columns are assigned by walking the turns rather than computed from the
    round number: with several passes in one session, pass 2 has to continue to
    the right of pass 1 instead of landing back on its columns.
    """
    columns: dict[tuple, int] = {}
    for turn in ordered:
        columns.setdefault(_column_key(turn), len(columns))
    return columns


def _column_key(turn: Turn) -> tuple:
    if turn.kind == "agent":
        return (turn.pass_no, "round", turn.round)
    return (turn.pass_no, turn.kind)


def _turn_node(turn: Turn, column: int) -> CanvasNode:
    return CanvasNode(
        id=str(turn.id),
        type=turn.kind,
        position={"x": float(column * X_STEP), "y": float(turn.agent_position * Y_STEP)},
        data={
            "label": _label(turn),
            "agent_name": turn.agent_name,
            "round": turn.round,
            "pass_no": turn.pass_no,
            "has_text": bool(turn.text),
        },
    )


def _label(turn: Turn) -> str:
    if turn.kind == "message":
        return turn.text
    head = f"{turn.agent_name} - R{turn.round}"
    return f"{head} - {turn.title}" if turn.title else head
