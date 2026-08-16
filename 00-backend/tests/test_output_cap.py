"""A hard ceiling on how much a turn may generate.

The word limit on an agent is an instruction, and a model is free to ignore it:
one was observed answering a 60-word brief with 7900 tokens and climbing, which
leaves a debate that never ends. The prompt still asks politely; this is the
floor under it.
"""

import httpx

from src.graph.builder import build_graph, initial_state
from src.llm.options import ChatOptions
from src.llm.provider import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    LMStudioProvider,
    OllamaProvider,
)
from src.llm.titles import TITLE_MAX_TOKENS, make_titler
from src.graph.nodes import token_budget
from tests.support import agent, make_deps, team


def _capturing_factory(calls: list[dict]):
    """Records the cap each node asks for."""

    class Fake:
        async def astream(self, messages):
            from langchain_core.messages import AIMessageChunk

            yield AIMessageChunk(content="reply")

        async def ainvoke(self, messages):
            from langchain_core.messages import AIMessage

            return AIMessage(content="a title")

    def factory(provider: str, model: str, options: ChatOptions | None = None):
        calls.append({"model": model, "max_tokens": (options or ChatOptions()).max_tokens})
        return Fake()

    return factory


async def _run(the_team, agents) -> list[dict]:
    calls: list[dict] = []
    graph = build_graph(the_team, agents, make_deps(llm_factory=_capturing_factory(calls)))
    await graph.ainvoke(initial_state("s1", "an idea", 1))
    return calls


def test_words_become_a_token_budget_with_room_to_spare():
    """Generous on purpose: this must never truncate an answer that behaved."""
    assert token_budget(60) > 60
    assert token_budget(None) is None


def test_a_longer_limit_gets_a_larger_budget():
    assert token_budget(120) > token_budget(60)


async def test_an_agent_with_a_word_limit_is_capped_by_it():
    speaker = agent(1, "Advocate", 0)
    speaker.max_output_length_in_words = 60

    calls = await _run(team(), [speaker])

    assert calls[0]["max_tokens"] == token_budget(60)


async def test_an_agent_without_a_limit_falls_back_to_the_engine_ceiling():
    """None reaches the provider, which substitutes its own ceiling."""
    calls = await _run(team(), [agent(1, "Advocate", 0)])

    assert calls[0]["max_tokens"] is None


async def test_the_synthesis_is_capped_by_its_own_limit():
    calls = await _run(team(synthesis_max_output_length_in_words=200), [agent(1, "A", 0)])

    assert calls[-1]["max_tokens"] == token_budget(200)


async def test_the_titler_asks_for_only_a_handful_of_tokens():
    """A title is eight words; a runaway one would stall every turn."""
    calls: list[dict] = []
    titler = make_titler(_capturing_factory(calls), "ollama", "small")

    await titler("some text to title")

    assert calls[0]["max_tokens"] == TITLE_MAX_TOKENS
    assert TITLE_MAX_TOKENS < 100


def _http(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _handler(request):
    return httpx.Response(200, json={"models": [], "data": []})


def test_ollama_turns_the_cap_into_num_predict():
    chat = OllamaProvider("http://localhost:11434", _http(_handler)).chat("m", ChatOptions(max_tokens=240))

    assert chat.num_predict == 240


def test_lm_studio_turns_the_cap_into_max_tokens():
    chat = LMStudioProvider("http://localhost:1234/v1", _http(_handler)).chat(
        "m", ChatOptions(max_tokens=240)
    )

    assert chat.max_tokens == 240


def test_an_engine_asked_for_nothing_still_imposes_a_ceiling():
    """The runaway happened on an agent that named no limit at all."""
    chat = OllamaProvider("http://localhost:11434", _http(_handler)).chat("m")

    assert chat.num_predict == DEFAULT_MAX_OUTPUT_TOKENS


def test_the_ceiling_can_be_raised_per_engine():
    provider = OllamaProvider(
        "http://localhost:11434", _http(_handler), max_output_tokens=4096
    )

    assert provider.chat("m").num_predict == 4096


# A cap alone was not enough. A thinking model spent all 240 tokens reasoning,
# emitted nothing into `content`, and stopped on `done_reason=length`: the
# runaway became an empty bubble instead of an endless one.


def test_thinking_is_off_by_default():
    """The transcript wants the answer, not the deliberation behind it."""
    chat = OllamaProvider("http://localhost:11434", _http(_handler)).chat("m")

    assert chat.reasoning is False


def test_thinking_can_be_turned_back_on():
    provider = OllamaProvider("http://localhost:11434", _http(_handler), thinking=True)

    assert provider.chat("m").reasoning is True
