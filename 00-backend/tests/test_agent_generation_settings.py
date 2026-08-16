"""Thinking and context window, chosen per agent.

Both were engine-wide before: thinking off for everyone, the context window left
to whatever the engine defaulted to. Neither is right for a mixed team - a
strategist reading a long transcript wants a wide window, ten personas voting in
one line do not, and one agent may be worth letting deliberate while the rest
answer straight.
"""

import aiosqlite
import httpx

from src.db.agents import AgentsRepository
from src.db.schema import apply_schema
from src.db.teams import TeamsRepository
from src.db.transfer import export_team, import_team
from src.graph.builder import build_graph, initial_state
from src.llm.options import ChatOptions
from src.llm.provider import DEFAULT_MAX_OUTPUT_TOKENS, OllamaProvider
from src.models import AgentCreate, AgentUpdate, TeamCreate
from tests.support import agent, make_deps, team


def _capturing(calls: list[ChatOptions]):
    class Fake:
        async def astream(self, messages):
            from langchain_core.messages import AIMessageChunk

            yield AIMessageChunk(content="reply")

    def factory(provider: str, model: str, options: ChatOptions | None = None):
        calls.append(options or ChatOptions())
        return Fake()

    return factory


async def _run(the_team, agents) -> list[ChatOptions]:
    calls: list[ChatOptions] = []
    graph = build_graph(the_team, agents, make_deps(llm_factory=_capturing(calls)))
    await graph.ainvoke(initial_state("s1", "an idea", 1))
    return calls


async def test_an_agent_carries_its_own_context_window():
    speaker = agent(1, "Advocate", 0)
    speaker.context_window_in_tokens = 32768

    calls = await _run(team(), [speaker])

    assert calls[0].context_window == 32768


async def test_an_agent_carries_its_own_thinking_choice():
    speaker = agent(1, "Advocate", 0)
    speaker.thinking = True

    calls = await _run(team(), [speaker])

    assert calls[0].thinking is True


async def test_an_agent_that_chooses_nothing_leaves_both_to_the_engine():
    calls = await _run(team(), [agent(1, "Advocate", 0)])

    assert calls[0].context_window is None
    assert calls[0].thinking is None


async def test_two_agents_can_disagree():
    """The whole point: a wide reader beside a narrow voter."""
    wide = agent(1, "Reader", 0)
    wide.context_window_in_tokens = 32768
    narrow = agent(2, "Voter", 1)
    narrow.context_window_in_tokens = 4096

    calls = await _run(team(), [wide, narrow])

    assert [c.context_window for c in calls[:2]] == [32768, 4096]


def _http() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"models": []}))
    )


def test_the_context_window_becomes_num_ctx():
    chat = OllamaProvider("http://x", _http()).chat("m", ChatOptions(context_window=32768))

    assert chat.num_ctx == 32768


def test_no_context_window_leaves_num_ctx_unset():
    """Unset means the engine's own default, not a number we invented."""
    chat = OllamaProvider("http://x", _http()).chat("m", ChatOptions())

    assert chat.num_ctx is None


def test_an_agent_can_turn_thinking_back_on_by_itself():
    chat = OllamaProvider("http://x", _http()).chat("m", ChatOptions(thinking=True))

    assert chat.reasoning is True


def test_an_unset_thinking_choice_follows_the_engine():
    off = OllamaProvider("http://x", _http()).chat("m", ChatOptions())
    on = OllamaProvider("http://x", _http(), thinking=True).chat("m", ChatOptions())

    assert off.reasoning is False
    assert on.reasoning is True


def test_the_output_ceiling_still_applies():
    chat = OllamaProvider("http://x", _http()).chat("m", ChatOptions())

    assert chat.num_predict == DEFAULT_MAX_OUTPUT_TOKENS


async def test_both_are_stored_and_can_be_cleared(conn):
    teams = TeamsRepository(conn)
    repo = AgentsRepository(conn)
    t = await teams.create(TeamCreate(name="Board", synthesis_prompt="x"))

    created = await repo.create(
        t.id,
        AgentCreate(
            name="Advocate",
            system_prompt="push back",
            model="m",
            thinking=True,
            context_window_in_tokens=32768,
        ),
    )
    cleared = await repo.update(
        created.id, AgentUpdate(thinking=None, context_window_in_tokens=None)
    )

    assert (created.thinking, created.context_window_in_tokens) == (True, 32768)
    assert (cleared.thinking, cleared.context_window_in_tokens) == (None, None)


async def test_an_agent_stored_without_them_keeps_them_empty(conn):
    teams = TeamsRepository(conn)
    repo = AgentsRepository(conn)
    t = await teams.create(TeamCreate(name="Board", synthesis_prompt="x"))

    created = await repo.create(
        t.id, AgentCreate(name="Advocate", system_prompt="push back", model="m")
    )

    assert created.thinking is None
    assert created.context_window_in_tokens is None


async def test_they_survive_an_export_and_import(conn):
    teams = TeamsRepository(conn)
    agents = AgentsRepository(conn)
    t = await teams.create(TeamCreate(name="Board", synthesis_prompt="x"))
    await agents.create(
        t.id,
        AgentCreate(
            name="Advocate",
            system_prompt="push back",
            model="m",
            thinking=False,
            context_window_in_tokens=8192,
        ),
    )

    imported = await import_team(conn, await export_team(conn, t.id))

    restored = (await agents.list_by_team(imported.id))[0]
    assert restored.thinking is False
    assert restored.context_window_in_tokens == 8192


OLD_AGENTS = """
CREATE TABLE agents (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  team_id       INTEGER NOT NULL,
  name          TEXT    NOT NULL,
  system_prompt TEXT    NOT NULL,
  model         TEXT    NOT NULL,
  position      INTEGER NOT NULL,
  enabled       INTEGER NOT NULL DEFAULT 1,
  created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


async def test_the_columns_are_added_to_an_older_database():
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.executescript(OLD_AGENTS)

        await apply_schema(conn)

        async with conn.execute("PRAGMA table_info(agents)") as cursor:
            columns = {row[1] for row in await cursor.fetchall()}
        assert {"thinking", "context_window_in_tokens"} <= columns


# The synthesis reads the whole transcript - the longest input of the debate -
# and it borrows the first agent's model. Giving it that agent's window too
# would be exactly backwards: ten personas set to 8k would starve the one node
# that actually needs room. So it carries its own, and inherits neither.


async def test_the_synthesis_carries_its_own_context_window():
    calls = await _run(team(synthesis_context_window_in_tokens=32768), [agent(1, "A", 0)])

    assert calls[-1].context_window == 32768


async def test_the_synthesis_does_not_inherit_the_agent_window():
    speaker = agent(1, "A", 0)
    speaker.context_window_in_tokens = 4096

    calls = await _run(team(), [speaker])

    assert calls[0].context_window == 4096
    assert calls[-1].context_window is None


async def test_the_synthesis_carries_its_own_thinking_choice():
    calls = await _run(team(synthesis_thinking=True), [agent(1, "A", 0)])

    assert calls[-1].thinking is True


async def test_the_team_stores_the_synthesis_settings(conn):
    repo = TeamsRepository(conn)

    created = await repo.create(
        TeamCreate(
            name="Panel",
            synthesis_prompt="count",
            synthesis_context_window_in_tokens=32768,
            synthesis_thinking=False,
        )
    )

    assert created.synthesis_context_window_in_tokens == 32768
    assert created.synthesis_thinking is False


async def test_the_synthesis_settings_survive_an_export_and_import(conn):
    teams = TeamsRepository(conn)
    created = await teams.create(
        TeamCreate(
            name="Panel",
            synthesis_prompt="count",
            synthesis_context_window_in_tokens=16384,
            synthesis_thinking=True,
        )
    )
    await AgentsRepository(conn).create(
        created.id, AgentCreate(name="Voice", system_prompt="vote", model="m")
    )

    imported = await import_team(conn, await export_team(conn, created.id))

    assert imported.synthesis_context_window_in_tokens == 16384
    assert imported.synthesis_thinking is True


async def test_duplicating_a_team_carries_every_setting(conn):
    """A copy that quietly drops settings is worse than no copy button."""
    teams = TeamsRepository(conn)
    agents = AgentsRepository(conn)
    source = await teams.create(
        TeamCreate(
            name="Panel",
            synthesis_prompt="count",
            synthesis_provider="lmstudio",
            synthesis_model="big",
            synthesis_context_window_in_tokens=16384,
            synthesis_thinking=True,
        )
    )
    await agents.create(
        source.id,
        AgentCreate(
            name="Voice",
            system_prompt="vote",
            model="m",
            context_window_in_tokens=8192,
            thinking=False,
        ),
    )

    copy = await teams.duplicate(source.id)

    assert copy.synthesis_provider == "lmstudio"
    assert copy.synthesis_model == "big"
    assert copy.synthesis_context_window_in_tokens == 16384
    assert copy.synthesis_thinking is True
    copied_agent = (await agents.list_by_team(copy.id))[0]
    assert copied_agent.context_window_in_tokens == 8192
    assert copied_agent.thinking is False
