import json

from fastapi import APIRouter, HTTPException, Request, Response, status
from sse_starlette.sse import EventSourceResponse

from src.db.agents import AgentsRepository
from src.db.passes import PassesRepository
from src.db.sessions import SessionsRepository
from src.db.snapshot import snapshot_of
from src.db.teams import TeamsRepository
from src.db.turns import SqliteTurnRecorder
from src.debate import start_debate, start_follow_up
from src.graph.builder import enabled_in_order
from src.graph.layout import build_canvas
from src.llm.readiness import ENGINE_DOWN, blockers, engine_needs
from src.models import (
    Agent,
    Session,
    SessionCreate,
    SessionDetail,
    SessionMessage,
    SessionStart,
    Team,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


async def _check_engines(deps, team: Team, agents: list[Agent]) -> None:
    """Refuses to start rather than failing halfway through.

    Stops at the first blocker: the dashboard is the place that lists them all.
    With two engines a missing model is the everyday mistake, not an exotic one,
    so the message names who wanted it and the model it wanted.
    """
    found = blockers(engine_needs(team, agents), await deps.engines.catalogue())
    if not found:
        return

    first = found[0]
    raise HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE
        if first.reason == ENGINE_DOWN
        else status.HTTP_422_UNPROCESSABLE_CONTENT,
        first.message,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def start_session(payload: SessionStart, request: Request):
    deps = request.app.state.deps
    conn = deps.conn

    team = await TeamsRepository(conn).get(payload.team_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")

    agents = await AgentsRepository(conn).list_by_team(team.id)
    if not enabled_in_order(agents):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "The team has no enabled agents"
        )

    await _check_engines(deps, team, enabled_in_order(agents))

    session = await SessionsRepository(conn).create(
        SessionCreate(
            idea=payload.idea,
            team_id=team.id,
            team_name=team.name,
            max_rounds=payload.max_rounds or team.default_max_rounds,
            team_snapshot=snapshot_of(team, agents),
        )
    )
    start_debate(deps, session, team, agents)
    return {"session_id": session.id}


@router.post("/{session_id}/stop", status_code=status.HTTP_204_NO_CONTENT)
async def stop_session(session_id: str, request: Request):
    """Asks a running debate to halt at the next token.

    Works even when no run is in memory: a backend restart leaves the row saying
    `running` with nothing left to finish it, and this is the way out.
    """
    deps = request.app.state.deps
    sessions = SessionsRepository(deps.conn)

    session = await sessions.get(session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    if session.status != "running":
        raise HTTPException(status.HTTP_409_CONFLICT, "The debate is not running")

    run = deps.hub.get(session_id)
    if run is None:
        await sessions.finish(session_id, status="stopped")
    else:
        run.request_stop()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{session_id}/messages", status_code=status.HTTP_201_CREATED)
async def add_message(session_id: str, payload: SessionMessage, request: Request):
    """Opens a further pass, carrying the earlier summaries.

    Naming a team hands the session over to it from this pass on.
    """
    deps = request.app.state.deps
    passes = PassesRepository(deps.conn)

    session = await SessionsRepository(deps.conn).get(session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    if session.status == "running":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "The debate is still running. Wait for it to finish."
        )

    # Whoever is about to argue is who gets checked, not who argued before.
    incoming = await _incoming_team(deps, payload.team_id)
    team, agents = incoming or await passes.current_team(session)
    await _check_engines(deps, team, enabled_in_order(agents))

    await start_follow_up(deps, session, payload.text, payload.max_rounds, incoming)
    return {"session_id": session.id}


async def _incoming_team(deps, team_id: int | None) -> tuple[Team, list[Agent]] | None:
    if team_id is None:
        return None

    team = await TeamsRepository(deps.conn).get(team_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")

    agents = await AgentsRepository(deps.conn).list_by_team(team.id)
    if not enabled_in_order(agents):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "The team has no enabled agents"
        )
    return team, agents


@router.get("", response_model=list[Session])
async def list_sessions(request: Request):
    return await SessionsRepository(request.app.state.deps.conn).list()


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, request: Request):
    conn = request.app.state.deps.conn
    session = await SessionsRepository(conn).get(session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")

    turns = await SqliteTurnRecorder(conn).list_by_session(session_id)
    passes = PassesRepository(conn)
    # From the snapshots, so a session reloaded long after still draws the
    # protocols it actually ran with - one per pass, since it may have changed
    # hands along the way.
    protocols = await passes.protocols(session)
    return SessionDetail(
        **session.model_dump(),
        turns=turns,
        canvas=build_canvas(session.idea, turns, protocols),
        passes=await passes.timeline(session),
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str, request: Request):
    deps = request.app.state.deps
    if not await SessionsRepository(deps.conn).delete(session_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    deps.hub.discard(session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{session_id}/stream")
async def stream_session(session_id: str, request: Request):
    run = request.app.state.deps.hub.get(session_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No debate is attached to this session")

    async def events():
        async for name, data in run.subscribe():
            yield {"event": name, "data": json.dumps(data, ensure_ascii=False)}

    return EventSourceResponse(events())
