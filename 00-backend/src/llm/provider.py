"""The local engines, behind one interface.

Ollama and LM Studio both run models on this machine, but they speak different
APIs: Ollama has its own, LM Studio serves the OpenAI shape. A provider hides
that difference so an agent only has to name which engine it wants.
"""

from typing import Protocol

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from src.llm.options import ChatOptions

DEFAULT_TEMPERATURE = 0.8

# The last line of defence against a model that will not stop. The prompt asks
# for a length and the agent's own limit tightens it; this is what applies when
# an agent names no limit, and it is deliberately roomy - a debate turn that
# legitimately needs 700 words still fits.
DEFAULT_MAX_OUTPUT_TOKENS = 1024


class UnknownProvider(Exception):
    pass


class Provider(Protocol):
    name: str
    label: str

    async def list_models(self) -> list[str]: ...

    async def is_available(self) -> bool: ...

    def chat(
        self,
        model: str,
        options: ChatOptions | None = None,
        temperature: float | None = None,
    ) -> BaseChatModel: ...


class _HttpProvider:
    """Shared plumbing: an engine is available when it answers its model list."""

    name: str
    label: str

    def __init__(
        self,
        base_url: str,
        http: httpx.AsyncClient,
        temperature: float = DEFAULT_TEMPERATURE,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        thinking: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._http = http
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._thinking = thinking

    def _cap(self, max_tokens: int | None) -> int:
        """Never unbounded: an unasked-for cap still lands on the ceiling."""
        return max_tokens or self._max_output_tokens

    def _thinks(self, thinking: bool | None) -> bool:
        """The agent decides; unset falls back to how the engine was set up."""
        return self._thinking if thinking is None else thinking

    async def is_available(self) -> bool:
        """An explicit ping: an immediate 503 beats a silent timeout halfway
        through a debate."""
        try:
            await self.list_models()
        except (httpx.HTTPError, ValueError, KeyError):
            return False
        return True

    async def list_models(self) -> list[str]:  # pragma: no cover - overridden
        raise NotImplementedError


class OllamaProvider(_HttpProvider):
    name = "ollama"
    label = "Ollama"

    async def list_models(self) -> list[str]:
        response = await self._http.get(f"{self.base_url}/api/tags")
        response.raise_for_status()
        return [model["name"] for model in response.json().get("models", [])]

    def chat(
        self,
        model: str,
        options: ChatOptions | None = None,
        temperature: float | None = None,
    ) -> BaseChatModel:
        options = options or ChatOptions()
        return ChatOllama(
            model=model,
            base_url=self.base_url,
            temperature=self._temperature if temperature is None else temperature,
            num_predict=self._cap(options.max_tokens),
            # Left as None the engine picks, and its default is usually far
            # below what the model supports - which truncates a long debate in
            # silence rather than with an error.
            num_ctx=options.context_window,
            # Left to the model, a thinking one spends the whole budget
            # deliberating and emits nothing at all: the reasoning never reaches
            # `content`, so the turn arrives empty. The transcript wants the
            # answer anyway, and reasoning in it would break the countable tags
            # some teams rely on.
            reasoning=self._thinks(options.thinking),
        )


class LMStudioProvider(_HttpProvider):
    """LM Studio serves the OpenAI API, so the OpenAI client drives it.

    The key is required by the client and ignored by LM Studio: nothing leaves
    this machine.
    """

    name = "lmstudio"
    label = "LM Studio"

    async def list_models(self) -> list[str]:
        response = await self._http.get(f"{self.base_url}/models")
        response.raise_for_status()
        return [model["id"] for model in response.json().get("data", [])]

    def chat(
        self,
        model: str,
        options: ChatOptions | None = None,
        temperature: float | None = None,
    ) -> BaseChatModel:
        # The OpenAI shape has no equivalent of num_ctx or of a thinking switch:
        # both are set on the model as it is loaded in LM Studio itself.
        options = options or ChatOptions()
        return ChatOpenAI(
            model=model,
            base_url=self.base_url,
            api_key="lm-studio",
            temperature=self._temperature if temperature is None else temperature,
            max_tokens=self._cap(options.max_tokens),
        )


class Engines:
    def __init__(self, providers: list[Provider]) -> None:
        self._providers = {provider.name: provider for provider in providers}

    def get(self, name: str) -> Provider | None:
        return self._providers.get(name)

    def require(self, name: str) -> Provider:
        provider = self.get(name)
        if provider is None:
            raise UnknownProvider(f"No engine named '{name}'")
        return provider

    def chat(
        self,
        provider: str,
        model: str,
        options: ChatOptions | None = None,
        temperature: float | None = None,
    ) -> BaseChatModel:
        return self.require(provider).chat(model, options, temperature)

    async def catalogue(self) -> list[dict]:
        """What the model pickers show. One engine being off is the normal
        case, not a failure, so it reports an empty list instead of raising."""
        entries = []
        for provider in self._providers.values():
            try:
                models = await provider.list_models()
            except Exception:
                models = []
            entries.append(
                {
                    "provider": provider.name,
                    "label": provider.label,
                    "available": bool(models) or await provider.is_available(),
                    "models": models,
                }
            )
        return entries
