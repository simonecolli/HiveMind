"""Short title for a turn.

This is a separate call from the main generation: if the agent itself had to
produce a structured field, the stream would show the user JSON being typed out
character by character instead of prose.
"""

from collections.abc import Callable

from langchain_core.messages import HumanMessage, SystemMessage

from src.llm.options import ChatOptions

MAX_TITLE_CHARS = 80

# Eight words, and a hard stop well past them. A title that ran away would
# stall every single turn behind it, since it is called once per turn.
TITLE_MAX_TOKENS = 48

# The title follows the language of the debate, which comes from the user's
# idea and the agent prompts rather than from the interface.
_PROMPT = (
    "Summarise the user's text as a title of 5 to 8 words, written in the same"
    " language as the text. Reply with the title alone: no quotation marks and"
    " no trailing punctuation."
)

_WRAPPERS = ('"', "'", "«", "»", "“", "”", "*", "`")


def clean_title(raw: str) -> str | None:
    """Small models add quotes, prefixes and extra lines."""
    title = raw.strip().splitlines()[0].strip() if raw.strip() else ""
    if not title:
        return None

    if ":" in title:
        head, _, tail = title.partition(":")
        if head.strip().lower() in {"title", "titolo"} and tail.strip():
            title = tail.strip()

    title = title.strip("".join(_WRAPPERS)).strip().rstrip(".").strip()
    if not title:
        return None

    if len(title) > MAX_TITLE_CHARS:
        title = title[: MAX_TITLE_CHARS - 1].rstrip() + "…"
    return title


def make_titler(llm_factory: Callable, provider: str, model: str):
    async def titler(text: str) -> str | None:
        if not text.strip():
            return None
        reply = await llm_factory(provider, model, ChatOptions(max_tokens=TITLE_MAX_TOKENS)).ainvoke(
            [SystemMessage(_PROMPT), HumanMessage(text)]
        )
        return clean_title(reply.content)

    return titler
