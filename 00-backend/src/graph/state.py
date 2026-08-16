import operator
from typing import Annotated, TypedDict

from src.models import Turn

# Repeated at the end of the user message, not only in the system prompt: it is
# the last thing the model reads, and a small one weighs that most. Observed
# drifting anyway when the prompt asks it to *produce* text rather than comment.
LANGUAGE_REMINDER = "Write your answer in the same language as the original idea above."


class DebateState(TypedDict):
    session_id: str
    idea: str
    # What drives this pass: the original idea on pass 1, the follow-up message
    # afterwards.
    prompt: str
    pass_no: int
    # Only the canvas needs them: a swarm round is drawn as a mesh, a relay as a
    # thread. Keyed by pass because a session that hands over to another team
    # can change protocol partway through, and the canvas holds every pass.
    protocols: dict[int, str]
    round: int
    max_rounds: int
    previous_syntheses: list[str]
    turns: Annotated[list[Turn], operator.add]


def initial_state(
    session_id: str,
    idea: str,
    max_rounds: int,
    *,
    prompt: str | None = None,
    pass_no: int = 1,
    protocol: str = "relay",
    previous_syntheses: list[str] | None = None,
    previous_protocols: dict[int, str] | None = None,
) -> DebateState:
    return DebateState(
        session_id=session_id,
        idea=idea,
        prompt=prompt if prompt is not None else idea,
        pass_no=pass_no,
        protocols={**(previous_protocols or {}), pass_no: protocol},
        round=1,
        max_rounds=max_rounds,
        previous_syntheses=previous_syntheses or [],
        turns=[],
    )


def render_context(state: DebateState) -> str:
    """The debate so far, as the agent whose turn it is sees it.

    Earlier passes travel as their summaries only. Carrying whole transcripts
    would fill a local model's context window and leave it rambling.
    """
    lines = [f"ORIGINAL IDEA: {state['idea']}", ""]
    lines += _follow_up_lines(state)
    if state["turns"]:
        lines.append("CONTRIBUTIONS SO FAR IN THIS PASS:")
        lines.extend(
            f"[{turn.agent_name} - round {turn.round}] {turn.text}" for turn in state["turns"]
        )
    else:
        lines.append("You are the first to speak.")
    lines += [
        "",
        f"This is round {state['round']} of {state['max_rounds']}.",
        LANGUAGE_REMINDER,
    ]
    return "\n".join(lines)


def render_synthesis_input(state: DebateState) -> str:
    lines = [f"ORIGINAL IDEA: {state['idea']}", ""]
    lines += _follow_up_lines(state)
    lines += ["DEBATE TO SUMMARISE:", render_transcript(state), "", LANGUAGE_REMINDER]
    return "\n".join(lines)


def render_transcript(state: DebateState) -> str:
    return "\n\n".join(
        f"[{turn.agent_name} - round {turn.round}]\n{turn.text}" for turn in state["turns"]
    )


def _follow_up_lines(state: DebateState) -> list[str]:
    if state["pass_no"] <= 1:
        return []
    lines = [f"NEW MESSAGE FROM THE USER: {state['prompt']}", ""]
    if state["previous_syntheses"]:
        lines.append("SUMMARIES OF THE EARLIER PASSES, IN ORDER:")
        lines.extend(
            f"{index}. {summary}"
            for index, summary in enumerate(state["previous_syntheses"], start=1)
        )
        lines.append("")
    return lines
