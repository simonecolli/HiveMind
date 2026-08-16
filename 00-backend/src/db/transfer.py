"""Moving a team in and out as a JSON file.

Import runs on the server rather than being composed from the client so that a
half-built team never survives a failure: everything is validated first, and a
write that fails still takes the freshly created team down with it.
"""

import aiosqlite

from src.db.agents import AgentsRepository
from src.db.teams import TeamsRepository
from src.models import AgentCreate, AgentExport, Team, TeamCreate, TeamExport


async def export_team(conn: aiosqlite.Connection, team_id: int) -> TeamExport | None:
    team = await TeamsRepository(conn).get(team_id)
    if team is None:
        return None

    agents = await AgentsRepository(conn).list_by_team(team_id)
    return TeamExport(
        name=team.name,
        description=team.description,
        default_max_rounds=team.default_max_rounds,
        synthesis_prompt=team.synthesis_prompt,
        synthesis_max_output_length_in_words=team.synthesis_max_output_length_in_words,
        synthesis_provider=team.synthesis_provider,
        synthesis_model=team.synthesis_model,
        synthesis_context_window_in_tokens=team.synthesis_context_window_in_tokens,
        synthesis_thinking=team.synthesis_thinking,
        protocol=team.protocol,
        agents=[
            AgentExport(
                name=agent.name,
                system_prompt=agent.system_prompt,
                provider=agent.provider,
                model=agent.model,
                max_output_length_in_words=agent.max_output_length_in_words,
                context_window_in_tokens=agent.context_window_in_tokens,
                thinking=agent.thinking,
                enabled=agent.enabled,
            )
            for agent in agents
        ],
    )


async def import_team(conn: aiosqlite.Connection, payload: TeamExport) -> Team:
    teams = TeamsRepository(conn)
    agents = AgentsRepository(conn)

    team = await teams.create(
        TeamCreate(
            name=await teams.available_name(payload.name),
            description=payload.description,
            default_max_rounds=payload.default_max_rounds,
            synthesis_prompt=payload.synthesis_prompt,
            synthesis_max_output_length_in_words=(
                payload.synthesis_max_output_length_in_words
            ),
            synthesis_provider=payload.synthesis_provider,
            synthesis_model=payload.synthesis_model,
            synthesis_context_window_in_tokens=(
                payload.synthesis_context_window_in_tokens
            ),
            synthesis_thinking=payload.synthesis_thinking,
            protocol=payload.protocol,
        )
    )

    try:
        for agent in payload.agents:
            await agents.create(
                team.id,
                AgentCreate(
                    name=agent.name,
                    system_prompt=agent.system_prompt,
                    provider=agent.provider,
                    model=agent.model,
                    max_output_length_in_words=agent.max_output_length_in_words,
                    context_window_in_tokens=agent.context_window_in_tokens,
                    thinking=agent.thinking,
                    enabled=agent.enabled,
                ),
            )
    except Exception:
        # Without this the list would keep a team holding only the agents that
        # made it through before the failure.
        await teams.delete(team.id)
        raise

    return team
