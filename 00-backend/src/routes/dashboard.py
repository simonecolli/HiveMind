"""The landing page's data: can I start, and what do I depend on."""

from fastapi import APIRouter, Request

from src.db.agents import AgentsRepository
from src.db.teams import TeamsRepository
from src.graph.builder import enabled_in_order
from src.llm.readiness import engine_needs, grouped

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
async def dashboard(request: Request):
    deps = request.app.state.deps
    catalogue = await deps.engines.catalogue()
    installed = {
        (entry["provider"], model) for entry in catalogue for model in entry["models"]
    }
    labels = {entry["provider"]: entry["label"] for entry in catalogue}

    teams = await TeamsRepository(deps.conn).list()
    agents_repo = AgentsRepository(deps.conn)
    debates = await _debates_per_team(deps.conn)

    rows = []
    usage: dict[tuple[str, str], dict] = {}
    for team in teams:
        agents = enabled_in_order(await agents_repo.list_by_team(team.id))
        found = (
            grouped(engine_needs(team, agents), catalogue)
            if agents
            # A team nobody speaks for is not "ready with no blockers": it
            # cannot run at all, and the reason belongs on the same line.
            else ["This team has no enabled agents."]
        )
        rows.append(
            {
                "id": team.id,
                "name": team.name,
                "protocol": team.protocol,
                "agents": len(agents),
                "debates": debates.get(team.id, 0),
                "ready": not found,
                "blockers": found,
            }
        )

        for agent in agents:
            key = (agent.provider, agent.model)
            entry = usage.setdefault(
                key,
                {
                    "provider": agent.provider,
                    "label": labels.get(agent.provider, agent.provider),
                    "model": agent.model,
                    "agents": 0,
                    "teams": 0,
                    "installed": key in installed,
                },
            )
            entry["agents"] += 1
        for key in {(a.provider, a.model) for a in agents}:
            usage[key]["teams"] += 1

    # Most used first, name breaking the tie: on a fresh install every count is
    # zero, and an order decided by chance would reshuffle on every reload.
    rows.sort(key=lambda r: (-r["debates"], r["name"].lower()))

    # Models are ranked by what it would cost you to lose one, not by how often
    # it ran: with a handful of debates on the clock, usage says nothing yet.
    ranked = sorted(usage.values(), key=lambda e: (-e["agents"], e["model"]))
    return {"engines": catalogue, "teams": rows, "models": ranked}


async def _debates_per_team(conn) -> dict[int, int]:
    """How many debates each team argued.

    Opening a session and being handed one partway both count, and a team that
    did both in the same session counts it once: the question is how often you
    reach for it, not how many rows it left behind.
    """
    async with conn.execute(
        "SELECT team_id, COUNT(DISTINCT session_id) AS n FROM ("
        "  SELECT team_id, id AS session_id FROM sessions WHERE team_id IS NOT NULL"
        "  UNION"
        "  SELECT team_id, session_id FROM session_passes WHERE team_id IS NOT NULL"
        ") GROUP BY team_id"
    ) as cursor:
        return {row["team_id"]: row["n"] for row in await cursor.fetchall()}
