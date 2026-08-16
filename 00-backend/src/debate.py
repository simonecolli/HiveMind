"""Runs a debate and fans out its events.

Events are buffered: the frontend issues the POST and only then opens the
stream, so without a buffer the first events would be lost.
It also lets a client attach to a debate that has already finished.
"""

import asyncio

from src.db.passes import PassesRepository
from src.db.sessions import SessionsRepository
from src.db.turns import SqliteTurnRecorder
from src.graph.builder import build_graph
from src.graph.deps import DebateDeps
from src.graph.errors import DebateStopped
from src.graph.state import DebateState, initial_state
from src.models import Agent, Session, Team

MESSAGE_AUTHOR = "You"


class Run:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []
        self.finished = False
        self.stop_requested = False
        self._updated = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def emit(self, event: str, data: dict) -> None:
        self.events.append((event, data))
        self._updated.set()

    def request_stop(self) -> None:
        """Cooperative: the nodes look at this between tokens."""
        self.stop_requested = True

    def close(self) -> None:
        self.finished = True
        self._updated.set()

    async def subscribe(self):
        """Replay the events collected so far, then follow the new ones."""
        index = 0
        while True:
            self._updated.clear()
            while index < len(self.events):
                yield self.events[index]
                index += 1
            if self.finished:
                return
            await self._updated.wait()


class DebateHub:
    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}

    def create(self, session_id: str) -> Run:
        run = Run()
        self._runs[session_id] = run
        return run

    def get(self, session_id: str) -> Run | None:
        return self._runs.get(session_id)

    def discard(self, session_id: str) -> None:
        self._runs.pop(session_id, None)


def start_debate(deps, session: Session, team: Team, agents: list[Agent]) -> Run:
    """First pass: the idea itself."""
    state = initial_state(
        session.id, session.idea, session.max_rounds, protocol=team.protocol
    )
    return _launch(deps, session, team, agents, state)


async def start_follow_up(
    deps,
    session: Session,
    text: str,
    max_rounds: int | None,
    incoming: tuple[Team, list[Agent]] | None = None,
) -> Run:
    """A further pass, carrying the earlier summaries.

    With `incoming` the session changes hands: that team argues from here on,
    and is snapshotted so a later edit or deletion cannot rewrite this thread.
    Without it the pass stays with whoever holds the floor.
    """
    recorder = SqliteTurnRecorder(deps.conn)
    passes = PassesRepository(deps.conn)
    history = await recorder.list_by_session(session.id)
    pass_no = max((turn.pass_no for turn in history), default=1) + 1

    # The message is recorded as a turn: that puts it in the transcript, on the
    # canvas and in the seq ordering without any special case.
    started = await recorder.start(
        session_id=session.id,
        agent_id=0,
        agent_name=MESSAGE_AUTHOR,
        agent_position=0,
        pass_no=pass_no,
        round=0,
        kind="message",
    )
    await recorder.finish(started.id, text, None)

    if incoming is not None:
        team, agents = incoming
        await passes.record(session.id, pass_no, team, agents)
        # The incoming team's own default, not the one the session opened with:
        # a desk configured for two rounds should not inherit the panel's one.
        rounds = max_rounds or team.default_max_rounds
    else:
        team, agents = await passes.team_for_pass(session, pass_no)
        rounds = max_rounds or session.max_rounds

    state = initial_state(
        session.id,
        session.idea,
        rounds,
        prompt=text,
        pass_no=pass_no,
        protocol=team.protocol,
        previous_syntheses=[t.text for t in history if t.kind == "synthesis"],
        previous_protocols=await passes.protocols(session),
    )
    await SessionsRepository(deps.conn).mark_running(session.id)
    return _launch(deps, session, team, agents, state)


def _launch(deps, session: Session, team: Team, agents: list[Agent], state: DebateState) -> Run:
    run = deps.hub.create(session.id)
    run._task = asyncio.create_task(_run_debate(deps, run, session, team, agents, state))
    return run


async def _run_debate(
    deps, run: Run, session: Session, team: Team, agents: list[Agent], state: DebateState
) -> None:
    sessions = SessionsRepository(deps.conn)
    debate_deps = DebateDeps(
        llm_factory=deps.llm_factory,
        titler=deps.titler,
        recorder=SqliteTurnRecorder(deps.conn),
        emitter=run,
        should_stop=lambda: run.stop_requested,
    )
    try:
        graph = build_graph(team, agents, debate_deps, checkpointer=deps.checkpointer)
        await run.emit(
            "session.start",
            {
                "session_id": session.id,
                # The team arguing this pass, which after a handover is no
                # longer the one the session opened with.
                "team_name": team.name,
                "max_rounds": state["max_rounds"],
                "pass_no": state["pass_no"],
                "agents": [
                    {"id": a.id, "name": a.name, "position": a.position}
                    for a in agents
                    if a.enabled
                ],
            },
        )
        await graph.ainvoke(
            state,
            # One thread per pass: a LangGraph thread that reached END cannot be
            # invoked again.
            config={"configurable": {"thread_id": f"{session.id}:{state['pass_no']}"}},
        )
        await sessions.finish(session.id, status="done")
        await run.emit("session.end", {"status": "done"})
    except DebateStopped:
        await sessions.finish(session.id, status="stopped")
        await run.emit("session.end", {"status": "stopped"})
    except Exception as exc:  # the debate failed; the session records it
        await sessions.finish(session.id, status="error", error=str(exc))
        await run.emit("error", {"message": str(exc), "detail": type(exc).__name__})
        await run.emit("session.end", {"status": "error"})
    finally:
        run.close()
