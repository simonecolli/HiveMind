from fastapi import APIRouter, HTTPException, Request, Response, status

from src.db.agents import AgentsRepository
from src.db.teams import TeamsRepository
from src.db.transfer import export_team, import_team
from src.models import (
    Agent,
    AgentCreate,
    ReorderRequest,
    Team,
    TeamCreate,
    TeamDetail,
    TeamExport,
    TeamUpdate,
)

router = APIRouter(prefix="/teams", tags=["teams"])


def _repos(request: Request) -> tuple[TeamsRepository, AgentsRepository]:
    conn = request.app.state.deps.conn
    return TeamsRepository(conn), AgentsRepository(conn)


@router.get("", response_model=list[Team])
async def list_teams(request: Request):
    teams, _ = _repos(request)
    return await teams.list()


@router.post("", response_model=Team, status_code=status.HTTP_201_CREATED)
async def create_team(payload: TeamCreate, request: Request):
    teams, _ = _repos(request)
    try:
        return await teams.create(payload)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post("/import", response_model=Team, status_code=status.HTTP_201_CREATED)
async def import_team_route(payload: TeamExport, request: Request):
    """Declared before `/{team_id}` so the literal path wins the match."""
    return await import_team(request.app.state.deps.conn, payload)


@router.get("/{team_id}/export", response_model=TeamExport)
async def export_team_route(team_id: int, request: Request):
    payload = await export_team(request.app.state.deps.conn, team_id)
    if payload is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    return payload


@router.get("/{team_id}", response_model=TeamDetail)
async def get_team(team_id: int, request: Request):
    teams, agents = _repos(request)
    team = await teams.get(team_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    return TeamDetail(**team.model_dump(), agents=await agents.list_by_team(team_id))


@router.patch("/{team_id}", response_model=Team)
async def update_team(team_id: int, payload: TeamUpdate, request: Request):
    teams, _ = _repos(request)
    if await teams.get(team_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    try:
        return await teams.update(team_id, payload)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(team_id: int, request: Request):
    teams, _ = _repos(request)
    if not await teams.delete(team_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{team_id}/duplicate", response_model=Team, status_code=status.HTTP_201_CREATED)
async def duplicate_team(team_id: int, request: Request):
    teams, _ = _repos(request)
    copy = await teams.duplicate(team_id)
    if copy is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    return copy


@router.post("/{team_id}/agents", response_model=Agent, status_code=status.HTTP_201_CREATED)
async def add_agent(team_id: int, payload: AgentCreate, request: Request):
    teams, agents = _repos(request)
    if await teams.get(team_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    return await agents.create(team_id, payload)


@router.post("/{team_id}/agents/reorder", response_model=list[Agent])
async def reorder_agents(team_id: int, payload: ReorderRequest, request: Request):
    teams, agents = _repos(request)
    if await teams.get(team_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    try:
        return await agents.reorder(team_id, payload.ordered_ids)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
