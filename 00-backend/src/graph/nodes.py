"""The debate nodes.

There is a single node function for agents, parameterised by the record: that
is what lets you add an agent from the UI without writing code.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from src.graph.deps import DebateDeps
from src.graph.errors import DebateStopped
from src.graph.layout import build_canvas
from src.graph.state import DebateState, render_context, render_synthesis_input
from src.llm.options import ChatOptions
from src.models import Agent, Turn

SYNTHESIS_NAME = "Synthesis"


# The prompts and the context scaffolding around them are written in English,
# while the idea often is not. Left to itself a small model drifts, and it does
# not always drift towards English.
LANGUAGE_RULE = (
    "Reply in the same language as the original idea, whatever language these"
    " instructions happen to be written in. The wording around you is scaffolding,"
    " not a request to switch language."
)


# Words to tokens, with room to spare. The point is to stop a runaway, not to
# police a length the prompt already asked for, so an answer that respected its
# brief never comes near this.
TOKENS_PER_WORD = 4


def token_budget(max_words: int | None) -> int | None:
    """The hard ceiling for a turn, or None to leave it to the engine's own."""
    return max_words * TOKENS_PER_WORD if max_words else None


def with_rules(prompt: str, max_words: int | None) -> str:
    """The prompt, plus the rules that hold for every agent of every team.

    Kept here rather than pasted into each team's text: it then covers the teams
    you already have and the ones you write later, and there is one place to
    change it. The length limit is a field for the same reason, and left empty it
    adds nothing at all, so a prompt that states its own limit is not
    contradicted by a second one.
    """
    parts = [prompt, LANGUAGE_RULE]
    if max_words:
        parts.append(f"Answer in {max_words} words at most.")
    return "\n\n".join(parts)


def make_agent_node(agent: Agent, deps: DebateDeps):
    async def node(state: DebateState) -> dict:
        turn = await _run_turn(
            deps,
            state,
            agent_id=agent.id,
            agent_name=agent.name,
            agent_position=agent.position,
            kind="agent",
            round=state["round"],
            provider=agent.provider,
            model=agent.model,
            options=ChatOptions(
                max_tokens=token_budget(agent.max_output_length_in_words),
                context_window=agent.context_window_in_tokens,
                thinking=agent.thinking,
            ),
            messages=[
                SystemMessage(
                    with_rules(agent.system_prompt, agent.max_output_length_in_words)
                ),
                HumanMessage(render_context(state)),
            ],
        )
        return {"turns": [turn]}

    return node


def make_synthesis_node(
    synthesis_prompt: str,
    provider: str,
    model: str,
    position: int,
    deps: DebateDeps,
    max_words: int | None = None,
    context_window: int | None = None,
    thinking: bool | None = None,
):
    async def node(state: DebateState) -> dict:
        turn = await _run_turn(
            deps,
            state,
            agent_id=0,
            agent_name=SYNTHESIS_NAME,
            agent_position=position,
            kind="synthesis",
            round=state["max_rounds"],
            provider=provider,
            model=model,
            # Its own, never the first agent's: this node reads the entire
            # transcript, while that agent may have been set narrow for a
            # one-line vote.
            options=ChatOptions(
                max_tokens=token_budget(max_words),
                context_window=context_window,
                thinking=thinking,
            ),
            messages=[
                SystemMessage(with_rules(synthesis_prompt, max_words)),
                HumanMessage(render_synthesis_input(state)),
            ],
        )
        return {"turns": [turn]}

    return node


async def round_start(state: DebateState) -> dict:
    """Single entry point of a round, in both protocols."""
    return {}


async def round_tick(state: DebateState) -> dict:
    return {"round": state["round"] + 1}


def should_continue(state: DebateState) -> str:
    return "loop" if state["round"] <= state["max_rounds"] else "end"


async def _run_turn(
    deps: DebateDeps,
    state: DebateState,
    *,
    agent_id: int,
    agent_name: str,
    agent_position: int,
    kind: str,
    round: int,
    provider: str,
    model: str,
    messages: list,
    options: ChatOptions | None = None,
) -> Turn:
    # Checked before anything is written, so a stop leaves no empty turn behind.
    if deps.should_stop():
        raise DebateStopped

    started = await deps.recorder.start(
        session_id=state["session_id"],
        agent_id=agent_id,
        agent_name=agent_name,
        agent_position=agent_position,
        pass_no=state["pass_no"],
        round=round,
        kind=kind,
    )
    turn_id, seq = started.id, started.seq
    await deps.emitter.emit(
        "turn.start",
        {
            "turn_id": turn_id,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "pass_no": state["pass_no"],
            "round": round,
            "seq": seq,
            "kind": kind,
        },
    )

    llm = deps.llm_factory(provider, model, options)
    chunks: list[str] = []
    stopped = False
    async for chunk in llm.astream(messages):
        if deps.should_stop():
            stopped = True
            break
        text = _chunk_text(chunk)
        if not text:
            continue
        chunks.append(text)
        await deps.emitter.emit("turn.delta", {"turn_id": turn_id, "text": text})

    # Whatever was written stays written: the reader watched it appear. But a
    # turn stopped before its first token has nothing to keep, and an empty
    # bubble in the transcript reads as a fault.
    text = "".join(chunks)
    if stopped and not text:
        await deps.recorder.discard(turn_id)
        await deps.emitter.emit("turn.discarded", {"turn_id": turn_id})
        raise DebateStopped

    title = None if stopped else await _safe_title(deps, text)
    await deps.recorder.finish(turn_id, text, title)
    await deps.emitter.emit("turn.end", {"turn_id": turn_id, "title": title})
    if stopped:
        raise DebateStopped

    turn = Turn(
        id=turn_id,
        agent_id=agent_id,
        agent_name=agent_name,
        agent_position=agent_position,
        pass_no=state["pass_no"],
        round=round,
        seq=seq,
        kind=kind,
        title=title,
        text=text,
    )
    # Built from what has actually been written, not from this node's own state:
    # in a swarm round the siblings are invisible to each other, and a canvas
    # built per node would drop theirs.
    canvas = build_canvas(
        state["idea"],
        await deps.recorder.list_by_session(state["session_id"]),
        state["protocols"],
    )
    await deps.emitter.emit("graph", canvas.model_dump())
    return turn


async def _safe_title(deps: DebateDeps, text: str) -> str | None:
    """The title is a garnish: if the model will not cooperate, the node shows
    just the agent and round, and the debate carries on."""
    try:
        return await deps.titler(text)
    except Exception:
        return None


def _chunk_text(chunk) -> str:
    content = getattr(chunk, "content", chunk)
    if isinstance(content, str):
        return content
    # Some providers return lists of typed blocks.
    return "".join(part.get("text", "") for part in content if isinstance(part, dict))
