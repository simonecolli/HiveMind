"""Two local engines behind one interface."""

import httpx
import pytest

from src.llm.provider import Engines, LMStudioProvider, OllamaProvider, UnknownProvider


def _http(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _ollama(handler) -> OllamaProvider:
    return OllamaProvider("http://localhost:11434", _http(handler))


def _lmstudio(handler) -> LMStudioProvider:
    return LMStudioProvider("http://localhost:1234/v1", _http(handler))


async def test_ollama_reads_the_names_from_its_tags():
    def handler(request):
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]})

    assert await _ollama(handler).list_models() == ["qwen2.5:7b"]


async def test_lm_studio_reads_the_ids_from_the_openai_route():
    def handler(request):
        assert request.url.path == "/v1/models"
        return httpx.Response(
            200, json={"data": [{"id": "google/gemma-4-e4b"}, {"id": "qwen3-coder-30b"}]}
        )

    models = await _lmstudio(handler).list_models()

    assert models == ["google/gemma-4-e4b", "qwen3-coder-30b"]


async def test_an_engine_that_refuses_the_connection_is_not_available():
    def handler(request):
        raise httpx.ConnectError("connection refused")

    assert await _lmstudio(handler).is_available() is False


async def test_an_engine_that_answers_is_available():
    def handler(request):
        return httpx.Response(200, json={"data": []})

    assert await _lmstudio(handler).is_available() is True


async def test_the_two_engines_keep_their_own_names():
    def handler(request):
        return httpx.Response(200, json={"models": [], "data": []})

    assert _ollama(handler).name == "ollama"
    assert _lmstudio(handler).name == "lmstudio"


async def test_the_catalogue_reports_each_engine_with_its_models():
    def ollama_up(request):
        return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]})

    def lmstudio_down(request):
        raise httpx.ConnectError("connection refused")

    engines = Engines([_ollama(ollama_up), _lmstudio(lmstudio_down)])

    catalogue = await engines.catalogue()

    assert catalogue == [
        {"provider": "ollama", "label": "Ollama", "available": True, "models": ["qwen2.5:7b"]},
        {"provider": "lmstudio", "label": "LM Studio", "available": False, "models": []},
    ]


async def test_a_stopped_engine_reports_no_models_instead_of_failing():
    """The catalogue must survive one engine being off: that is the normal case."""

    def down(request):
        raise httpx.ConnectError("connection refused")

    engines = Engines([_lmstudio(down)])

    assert (await engines.catalogue())[0]["models"] == []


async def test_asking_for_an_unknown_engine_is_an_error():
    engines = Engines([])

    with pytest.raises(UnknownProvider, match="lmstudio"):
        engines.chat("lmstudio", "google/gemma-4-e4b")


async def test_each_engine_builds_a_chat_model_for_its_own_kind():
    def handler(request):
        return httpx.Response(200, json={"models": [], "data": []})

    engines = Engines([_ollama(handler), _lmstudio(handler)])

    assert type(engines.chat("ollama", "qwen2.5:7b")).__name__ == "ChatOllama"
    assert type(engines.chat("lmstudio", "google/gemma-4-e4b")).__name__ == "ChatOpenAI"
