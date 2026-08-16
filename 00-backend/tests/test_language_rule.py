"""Every agent is told to answer in the language of the idea.

The prompts and the context scaffolding are written in English while the idea
often is not. Left to itself a small model drifts, sometimes to a language
nobody asked for.
"""

from src.graph.builder import build_graph, initial_state
from src.graph.nodes import LANGUAGE_RULE
from tests.support import agent, make_deps, recording_llm_factory, system_prompts, team


async def _run(*, agents=None, the_team=None, deps=None):
    deps = deps or make_deps()
    graph = build_graph(the_team or team(), agents or [agent(1, "Advocate", 0)], deps)
    await graph.ainvoke(initial_state("s1", "un'idea in italiano", 1))


async def test_every_agent_is_told_to_keep_the_language():
    sink: list[list] = []
    deps = make_deps(llm_factory=recording_llm_factory(sink))

    await _run(agents=[agent(1, "Alfa", 0), agent(2, "Beta", 1)], deps=deps)

    agent_prompts = [p for p in system_prompts(sink) if "you are" in p]
    assert agent_prompts
    assert all(LANGUAGE_RULE in prompt for prompt in agent_prompts)


async def test_the_synthesis_is_told_too():
    """It reads several turns at once, so it drifts more easily than anyone."""
    sink: list[list] = []
    deps = make_deps(llm_factory=recording_llm_factory(sink))

    await _run(deps=deps)

    assert LANGUAGE_RULE in system_prompts(sink)[-1]


async def test_the_rule_is_added_without_touching_the_prompt():
    sink: list[list] = []
    deps = make_deps(llm_factory=recording_llm_factory(sink))

    await _run(deps=deps)

    assert system_prompts(sink)[0].startswith("you are Advocate")


async def test_the_rule_sits_alongside_the_length_limit():
    sink: list[list] = []
    deps = make_deps(llm_factory=recording_llm_factory(sink))
    speaker = agent(1, "Advocate", 0)
    speaker.max_output_length_in_words = 40

    await _run(agents=[speaker], deps=deps)

    prompt = system_prompts(sink)[0]
    assert LANGUAGE_RULE in prompt
    assert "40 words" in prompt
