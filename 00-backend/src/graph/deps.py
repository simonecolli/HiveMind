"""Dependencies injected into the graph nodes.

They are explicit for one precise reason: they make the debate runnable in
tests with no Ollama running and no database, by swapping the LLM, the
persistence and the event sink.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import NamedTuple, Protocol

from langchain_core.language_models import BaseChatModel

from src.llm.options import ChatOptions


class StartedTurn(NamedTuple):
    """`seq` is allocated by the recorder, not computed by the caller.

    With a swarm round the agents run in the same superstep and all see the same
    state, so anyone counting turns in memory would hand out the same number
    several times over.
    """

    id: int
    seq: int


class TurnRecorder(Protocol):
    async def start(
        self,
        *,
        session_id: str,
        agent_id: int,
        agent_name: str,
        agent_position: int,
        pass_no: int,
        round: int,
        kind: str,
    ) -> StartedTurn:
        """Record the start of a turn and return its id and order."""

    async def finish(self, turn_id: int, text: str, title: str | None) -> None:
        """Complete the turn with its text and title."""

    async def discard(self, turn_id: int) -> None:
        """Drop a turn that produced nothing, so it leaves no empty trace."""

    async def list_by_session(self, session_id: str) -> list:
        """Every turn written so far, in order."""


class Emitter(Protocol):
    async def emit(self, event: str, data: dict) -> None: ...


@dataclass
class DebateDeps:
    # (provider, model, options) -> chat model. Every option left None means
    # "use the engine's own", never "unbounded".
    llm_factory: Callable[[str, str, ChatOptions | None], BaseChatModel]
    titler: Callable[[str], Awaitable[str | None]]
    recorder: TurnRecorder
    emitter: Emitter
    # Checked between turns and between tokens, so a stop lands within a token
    # rather than at the end of a whole turn.
    should_stop: Callable[[], bool] = lambda: False
