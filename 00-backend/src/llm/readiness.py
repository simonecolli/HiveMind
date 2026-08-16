"""Whether a team could actually run, and why not.

The same question is asked in two places with different appetites. Starting a
session wants the first reason to stop; the dashboard wants the whole bill, for
every team, before you have picked one. Both read the engine catalogue the same
way, so the reading lives here and the callers decide what to do with it.
"""

from dataclasses import dataclass

from src.models import Agent, Team

ENGINE_DOWN = "engine_down"
MODEL_MISSING = "model_missing"
NO_AGENTS = "no_agents"


@dataclass(frozen=True)
class Need:
    """One (who, engine, model) that has to be up before a word is written."""

    who: str
    provider: str
    model: str


@dataclass(frozen=True)
class Blocker:
    reason: str
    message: str


def engine_needs(team: Team, agents: list[Agent]) -> list[Need]:
    """The synthesis is listed separately only when the team names its own:
    left empty it runs on the first agent's, which is already in the list."""
    needs = [Need(agent.name, agent.provider, agent.model) for agent in agents]
    if agents and (team.synthesis_provider or team.synthesis_model):
        needs.append(
            Need(
                "The synthesis",
                team.synthesis_provider or agents[0].provider,
                team.synthesis_model or agents[0].model,
            )
        )
    return needs


def blockers(needs: list[Need], catalogue: list[dict]) -> list[Blocker]:
    """Everything standing between this team and a first token, in order."""
    engines = {entry["provider"]: entry for entry in catalogue}
    found: list[Blocker] = []

    for need in needs:
        engine = engines.get(need.provider)
        label = engine["label"] if engine else need.provider
        if engine is None or not engine["available"]:
            found.append(
                Blocker(
                    ENGINE_DOWN,
                    f"{need.who} runs on {label}, which is not responding."
                    " Start it and retry.",
                )
            )
        elif need.model not in engine["models"]:
            found.append(
                Blocker(
                    MODEL_MISSING,
                    f"{need.who} needs the model '{need.model}',"
                    f" which {label} does not have.",
                )
            )
    return found


def grouped(needs: list[Need], catalogue: list[dict]) -> list[str]:
    """One line per problem, not per agent.

    Three agents on one dead engine is a single thing to go and fix; repeating
    the same sentence three times buries it. The session route keeps the
    per-agent wording, which is right there: it names the one that stopped it.
    """
    engines = {entry["provider"]: entry for entry in catalogue}
    counts: dict[tuple[str, str, str], int] = {}

    for need in needs:
        engine = engines.get(need.provider)
        label = engine["label"] if engine else need.provider
        if engine is None or not engine["available"]:
            key = (ENGINE_DOWN, label, "")
        elif need.model not in engine["models"]:
            key = (MODEL_MISSING, label, need.model)
        else:
            continue
        counts[key] = counts.get(key, 0) + 1

    lines = []
    for (reason, label, model), n in counts.items():
        who = f"{n} agent" if n == 1 else f"{n} agents"
        if reason == ENGINE_DOWN:
            lines.append(f"{label} is not responding, and {who} need it. Start it and retry.")
        else:
            lines.append(f"{label} does not have '{model}', which {who} ask for.")
    return lines
