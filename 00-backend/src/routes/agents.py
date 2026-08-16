from fastapi import APIRouter, HTTPException, Request, Response, status

from src.db.agents import AgentsRepository
from src.models import Agent, AgentUpdate

router = APIRouter(prefix="/agents", tags=["agents"])


def _repo(request: Request) -> AgentsRepository:
    return AgentsRepository(request.app.state.deps.conn)


@router.patch("/{agent_id}", response_model=Agent)
async def update_agent(agent_id: int, payload: AgentUpdate, request: Request):
    repo = _repo(request)
    if await repo.get(agent_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    return await repo.update(agent_id, payload)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(agent_id: int, request: Request):
    if not await _repo(request).delete(agent_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
