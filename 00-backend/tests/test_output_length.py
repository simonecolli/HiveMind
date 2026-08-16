"""The output length lives in its own field, not buried in the prompt text."""

import aiosqlite

from src.db.agents import AgentsRepository
from src.db.schema import apply_schema
from src.db.teams import TeamsRepository
from src.graph.builder import build_graph, initial_state
from src.models import AgentCreate, AgentUpdate, TeamCreate, TeamUpdate
from tests.support import agent, make_deps, recording_llm_factory, system_prompts, team


async def _run(agents, *, the_team=None, deps=None):
    deps = deps or make_deps()
    graph = build_graph(the_team or team(), agents, deps)
    await graph.ainvoke(initial_state("s1", "an idea", 1))


async def test_an_agent_can_be_stored_without_a_limit(conn):
    teams = TeamsRepository(conn)
    repo = AgentsRepository(conn)
    t = await teams.create(TeamCreate(name="Board", synthesis_prompt="x"))

    created = await repo.create(
        t.id, AgentCreate(name="Advocate", system_prompt="push back", model="m")
    )

    assert created.max_output_length_in_words is None


async def test_an_agent_keeps_the_limit_it_was_given(conn):
    teams = TeamsRepository(conn)
    repo = AgentsRepository(conn)
    t = await teams.create(TeamCreate(name="Board", synthesis_prompt="x"))

    created = await repo.create(
        t.id,
        AgentCreate(
            name="Advocate",
            system_prompt="push back",
            model="m",
            max_output_length_in_words=120,
        ),
    )

    assert created.max_output_length_in_words == 120


async def test_the_limit_can_be_changed_and_cleared(conn):
    teams = TeamsRepository(conn)
    repo = AgentsRepository(conn)
    t = await teams.create(TeamCreate(name="Board", synthesis_prompt="x"))
    created = await repo.create(
        t.id,
        AgentCreate(
            name="Advocate", system_prompt="push back", model="m", max_output_length_in_words=120
        ),
    )

    raised = await repo.update(created.id, AgentUpdate(max_output_length_in_words=50))
    cleared = await repo.update(created.id, AgentUpdate(max_output_length_in_words=None))

    assert raised.max_output_length_in_words == 50
    assert cleared.max_output_length_in_words is None


async def test_the_limit_reaches_the_model_as_an_instruction():
    sink: list[list] = []
    deps = make_deps(llm_factory=recording_llm_factory(sink))
    speaker = agent(1, "Advocate", 0)
    speaker.max_output_length_in_words = 120

    await _run([speaker], deps=deps)

    assert "120 words" in system_prompts(sink)[0]


async def test_no_length_sentence_is_added_without_a_limit():
    """The prompt keeps its own wording; only the shared rules follow it."""
    sink: list[list] = []
    deps = make_deps(llm_factory=recording_llm_factory(sink))

    await _run([agent(1, "Advocate", 0)], deps=deps)

    prompt = system_prompts(sink)[0]
    assert prompt.startswith("you are Advocate")
    assert "words at most" not in prompt


async def test_the_synthesis_limit_reaches_the_model():
    sink: list[list] = []
    deps = make_deps(llm_factory=recording_llm_factory(sink))
    the_team = team(synthesis_max_output_length_in_words=40)

    await _run([agent(1, "Advocate", 0)], the_team=the_team, deps=deps)

    assert "40 words" in system_prompts(sink)[-1]


async def test_no_length_sentence_is_added_to_the_synthesis_without_a_limit():
    sink: list[list] = []
    deps = make_deps(llm_factory=recording_llm_factory(sink))

    await _run([agent(1, "Advocate", 0)], deps=deps)

    prompt = system_prompts(sink)[-1]
    assert prompt.startswith("Synthesise the debate.")
    assert "words at most" not in prompt


async def test_a_team_carries_its_own_synthesis_limit(conn):
    repo = TeamsRepository(conn)

    created = await repo.create(
        TeamCreate(
            name="Board", synthesis_prompt="x", synthesis_max_output_length_in_words=40
        )
    )
    cleared = await repo.update(
        created.id, TeamUpdate(synthesis_max_output_length_in_words=None)
    )

    assert created.synthesis_max_output_length_in_words == 40
    assert cleared.synthesis_max_output_length_in_words is None


async def test_the_limits_survive_an_export_and_import(conn):
    from src.db.transfer import export_team, import_team

    teams = TeamsRepository(conn)
    agents = AgentsRepository(conn)
    t = await teams.create(
        TeamCreate(name="Board", synthesis_prompt="x", synthesis_max_output_length_in_words=40)
    )
    await agents.create(
        t.id,
        AgentCreate(
            name="Advocate", system_prompt="push back", model="m", max_output_length_in_words=120
        ),
    )

    imported = await import_team(conn, await export_team(conn, t.id))

    assert imported.synthesis_max_output_length_in_words == 40
    assert (await agents.list_by_team(imported.id))[0].max_output_length_in_words == 120


OLD_TABLES = """
CREATE TABLE teams (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  name               TEXT    NOT NULL UNIQUE,
  description        TEXT,
  default_max_rounds INTEGER NOT NULL DEFAULT 2,
  synthesis_prompt   TEXT    NOT NULL,
  created_at         TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE agents (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  team_id       INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  name          TEXT    NOT NULL,
  system_prompt TEXT    NOT NULL,
  model         TEXT    NOT NULL,
  position      INTEGER NOT NULL,
  enabled       INTEGER NOT NULL DEFAULT 1,
  created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


async def test_both_columns_are_added_to_an_older_database():
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.executescript(OLD_TABLES)

        await apply_schema(conn)

        async def columns(table: str) -> set[str]:
            async with conn.execute(f"PRAGMA table_info({table})") as cursor:
                return {row[1] for row in await cursor.fetchall()}

        assert "max_output_length_in_words" in await columns("agents")
        assert "synthesis_max_output_length_in_words" in await columns("teams")
