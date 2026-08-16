from langgraph.graph import END, StateGraph

from src.graph.deps import DebateDeps
from src.graph.nodes import (
    make_agent_node,
    make_synthesis_node,
    round_start,
    round_tick,
    should_continue,
)
from src.graph.state import DebateState, initial_state
from src.models import Agent, Team

__all__ = ["build_graph", "initial_state", "enabled_in_order"]


def enabled_in_order(agents: list[Agent]) -> list[Agent]:
    return sorted((a for a in agents if a.enabled), key=lambda a: a.position)


def build_graph(team: Team, agents: list[Agent], deps: DebateDeps, checkpointer=None):
    """Compile the debate graph for a team.

    Called at the start of every session, not at server startup: that is how an
    agent added from the UI joins in without a restart.
    """
    ordered = enabled_in_order(agents)
    if not ordered:
        raise ValueError("The team has no enabled agents")

    graph = StateGraph(DebateState)
    for agent in ordered:
        graph.add_node(_node_name(agent), make_agent_node(agent, deps))
    graph.add_node("round_tick", round_tick)
    graph.add_node(
        "synthesis",
        make_synthesis_node(
            team.synthesis_prompt,
            # The team may name its own; left empty the synthesis borrows the
            # first speaker's. A panel of small voices can then hand its tally
            # to a model big enough to count, without promoting one voter and
            # skewing the very vote it is counting.
            provider=team.synthesis_provider or ordered[0].provider,
            model=team.synthesis_model or ordered[0].model,
            position=len(ordered),
            deps=deps,
            max_words=team.synthesis_max_output_length_in_words,
            context_window=team.synthesis_context_window_in_tokens,
            thinking=team.synthesis_thinking,
        ),
    )

    # A pass-through node so a round has one entry point in both protocols, and
    # the loop has one place to come back to.
    graph.add_node("round_start", round_start)
    graph.set_entry_point("round_start")

    if team.protocol == "swarm":
        # Every agent hangs off the same node, so LangGraph runs them in one
        # superstep. Each of them sees the state as it was when the round began,
        # which is precisely "do not read your neighbours this round".
        for agent in ordered:
            graph.add_edge("round_start", _node_name(agent))
            graph.add_edge(_node_name(agent), "round_tick")
    else:
        graph.add_edge("round_start", _node_name(ordered[0]))
        for previous, following in zip(ordered, ordered[1:]):
            graph.add_edge(_node_name(previous), _node_name(following))
        graph.add_edge(_node_name(ordered[-1]), "round_tick")

    graph.add_conditional_edges(
        "round_tick",
        should_continue,
        {"loop": "round_start", "end": "synthesis"},
    )
    graph.add_edge("synthesis", END)

    return graph.compile(checkpointer=checkpointer)


def _node_name(agent: Agent) -> str:
    # `:` is a reserved character in LangGraph node names.
    return f"agent_{agent.id}"
