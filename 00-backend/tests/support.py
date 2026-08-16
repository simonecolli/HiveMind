"""Fake dependencies to exercise the graph without Ollama or a database."""

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessageChunk

from src.graph.deps import DebateDeps, StartedTurn
from src.models import Turn as TurnModel
from src.models import Agent, AgentCreate, Team, TeamCreate


class StubEngines:
    """A catalogue with no engine behind it."""

    def __init__(self, catalogue=None) -> None:
        self._catalogue = catalogue or [
            {"provider": "ollama", "label": "Ollama", "available": True, "models": ["m"]}
        ]

    async def catalogue(self):
        return self._catalogue


async def collect_events(client, session_id) -> list[str]:
    """SSE event names, in arrival order."""
    events: list[str] = []
    async with client.stream("GET", f"/api/v1/sessions/{session_id}/stream") as response:
        assert response.status_code == 200
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                events.append(line.split(":", 1)[1].strip())
    return events


class RecordingEmitter:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def emit(self, event: str, data: dict) -> None:
        self.events.append((event, data))

    def names(self) -> list[str]:
        return [name for name, _ in self.events]

    def payloads(self, event: str) -> list[dict]:
        return [data for name, data in self.events if name == event]


class InMemoryRecorder:
    """Hands out incrementing ids, the way SQLite's AUTOINCREMENT would."""

    def __init__(self) -> None:
        self.started: list[dict] = []
        self.finished: list[dict] = []
        self.discarded: list[int] = []
        self._next_id = 1
        self._rows: dict[int, dict] = {}

    async def start(self, **fields) -> StartedTurn:
        turn_id = self._next_id
        self._next_id += 1
        seq = len(self._rows)
        record = {"id": turn_id, "seq": seq, **fields}
        self.started.append(record)
        self._rows[turn_id] = record
        return StartedTurn(turn_id, seq)

    async def finish(self, turn_id: int, text: str, title: str | None) -> None:
        self.finished.append({"id": turn_id, "text": text, "title": title})
        self._rows[turn_id].update(text=text, title=title)

    async def discard(self, turn_id: int) -> None:
        self.discarded.append(turn_id)
        self._rows.pop(turn_id, None)

    async def list_by_session(self, session_id: str) -> list[TurnModel]:
        return [
            TurnModel(
                id=r["id"],
                agent_id=r["agent_id"],
                agent_name=r["agent_name"],
                agent_position=r["agent_position"],
                pass_no=r["pass_no"],
                round=r["round"],
                seq=r["seq"],
                kind=r["kind"],
                title=r.get("title"),
                text=r.get("text", ""),
            )
            for r in sorted(self._rows.values(), key=lambda r: r["seq"])
        ]


class RecordingLLM:
    """Captures the messages it is handed, then answers with fixed text.

    The node only ever calls `astream`, so duck typing is enough and the test
    can assert on what the model actually received.
    """

    def __init__(self, sink: list[list], text: str) -> None:
        self._sink = sink
        self._text = text

    async def astream(self, messages):
        self._sink.append(messages)
        yield AIMessageChunk(content=self._text)


def recording_llm_factory(sink: list[list], text: str = "reply"):
    def factory(provider: str, model: str, options=None):
        return RecordingLLM(sink, text)

    return factory


def system_prompts(sink: list[list]) -> list[str]:
    """The system message of every call, in order."""
    return [str(messages[0].content) for messages in sink]


def echo_llm_factory(replies: dict[str, str] | None = None):
    """Every call returns a fresh model, so the replies do not cycle."""

    def factory(provider: str, model: str, options=None):
        text = (replies or {}).get(model, f"reply from {model}")
        return FakeListChatModel(responses=[text])

    return factory


async def fixed_titler(text: str) -> str | None:
    return "title"


async def failing_titler(text: str) -> str | None:
    raise RuntimeError("the model is not responding")


def never_stop() -> bool:
    return False


def stop_after(checks: int):
    """A stop that trips on the n-th check, so a test can halt a debate at a
    known point instead of racing it."""
    seen = {"n": 0}

    def should_stop() -> bool:
        seen["n"] += 1
        return seen["n"] > checks

    return should_stop


def make_deps(
    *,
    llm_factory=None,
    titler=fixed_titler,
    recorder=None,
    emitter=None,
    should_stop=never_stop,
) -> DebateDeps:
    return DebateDeps(
        llm_factory=llm_factory or echo_llm_factory(),
        titler=titler,
        recorder=recorder or InMemoryRecorder(),
        emitter=emitter or RecordingEmitter(),
        should_stop=should_stop,
    )


def team(**kwargs) -> Team:
    base = dict(
        id=1,
        name="Board",
        description=None,
        default_max_rounds=1,
        synthesis_prompt="Synthesise the debate.",
        protocol="relay",
        synthesis_max_output_length_in_words=None,
        created_at="2026-08-12",
        updated_at="2026-08-12",
    )
    return Team(**{**base, **kwargs})


def agent(agent_id: int, name: str, position: int, *, enabled: bool = True, model: str = "m") -> Agent:
    return Agent(
        id=agent_id,
        team_id=1,
        name=name,
        system_prompt=f"you are {name}",
        max_output_length_in_words=None,
        provider="ollama",
        model=model,
        position=position,
        enabled=enabled,
        created_at="2026-08-12",
        updated_at="2026-08-12",
    )


__all__ = [
    "AgentCreate",
    "StubEngines",
    "collect_events",
    "TeamCreate",
    "InMemoryRecorder",
    "RecordingEmitter",
    "agent",
    "echo_llm_factory",
    "failing_titler",
    "fixed_titler",
    "make_deps",
    "team",
]
