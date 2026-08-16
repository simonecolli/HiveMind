"""Columns added to an existing database.

There is no versioned migration chain, but dropping the file is not an option
once it holds teams somebody wrote by hand.
"""

import aiosqlite

from src.db.schema import apply_schema

OLD_TURNS = """
CREATE TABLE sessions (
  id            TEXT    PRIMARY KEY,
  idea          TEXT    NOT NULL,
  team_id       INTEGER,
  team_name     TEXT    NOT NULL,
  max_rounds    INTEGER NOT NULL,
  team_snapshot TEXT    NOT NULL,
  status        TEXT    NOT NULL,
  error         TEXT,
  created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
  finished_at   TEXT
);

CREATE TABLE turns (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id     TEXT    NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  agent_id       INTEGER NOT NULL,
  agent_name     TEXT    NOT NULL,
  agent_position INTEGER NOT NULL,
  round          INTEGER NOT NULL,
  seq            INTEGER NOT NULL,
  kind           TEXT    NOT NULL DEFAULT 'agent',
  title          TEXT,
  text           TEXT    NOT NULL DEFAULT '',
  created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


async def _columns(conn: aiosqlite.Connection, table: str) -> set[str]:
    async with conn.execute(f"PRAGMA table_info({table})") as cursor:
        return {row[1] for row in await cursor.fetchall()}


async def test_pass_no_is_added_to_an_existing_turns_table():
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.executescript(OLD_TURNS)

        await apply_schema(conn)

        assert "pass_no" in await _columns(conn, "turns")


async def test_existing_turns_land_on_the_first_pass():
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.executescript(OLD_TURNS)
        await conn.execute(
            "INSERT INTO sessions (id, idea, team_name, max_rounds, team_snapshot, status)"
            " VALUES ('s1', 'an idea', 'Board', 2, '{}', 'done')"
        )
        await conn.execute(
            "INSERT INTO turns (session_id, agent_id, agent_name, agent_position, round, seq)"
            " VALUES ('s1', 1, 'Advocate', 0, 1, 0)"
        )
        await conn.commit()

        await apply_schema(conn)

        async with conn.execute("SELECT pass_no FROM turns") as cursor:
            rows = await cursor.fetchall()
        assert [row["pass_no"] for row in rows] == [1]


async def test_the_handover_table_is_created_on_an_older_database():
    """A database written before handovers existed has none of it."""
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.executescript(OLD_TURNS)

        await apply_schema(conn)

        assert await _columns(conn, "session_passes") == {
            "session_id",
            "pass_no",
            "team_id",
            "team_name",
            "team_snapshot",
            "created_at",
        }


async def test_deleting_a_session_takes_its_handovers_with_it():
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await apply_schema(conn)
        await conn.execute(
            "INSERT INTO sessions (id, idea, team_name, max_rounds, team_snapshot, status)"
            " VALUES ('s1', 'an idea', 'Panel', 2, '{}', 'done')"
        )
        await conn.execute(
            "INSERT INTO session_passes (session_id, pass_no, team_id, team_name, team_snapshot)"
            " VALUES ('s1', 2, 7, 'Desk', '{}')"
        )
        await conn.commit()

        await conn.execute("DELETE FROM sessions WHERE id = 's1'")

        async with conn.execute("SELECT COUNT(*) AS n FROM session_passes") as cursor:
            assert (await cursor.fetchone())["n"] == 0


async def test_applying_the_schema_twice_is_harmless():
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await apply_schema(conn)

        await apply_schema(conn)

        assert "pass_no" in await _columns(conn, "turns")
