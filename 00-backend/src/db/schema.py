"""Schema for `hivemind.db`.

The schema is applied idempotently at startup. There is no versioned migration
system: while the project stays local and single-user, recreating the file
beats maintaining a chain of migrations.
"""

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  name               TEXT    NOT NULL UNIQUE,
  description        TEXT,
  default_max_rounds INTEGER NOT NULL DEFAULT 2,
  synthesis_prompt   TEXT    NOT NULL,
  synthesis_max_output_length_in_words INTEGER,
  synthesis_provider TEXT,                     -- empty: the first agent's
  synthesis_model    TEXT,                     -- empty: the first agent's
  synthesis_context_window_in_tokens INTEGER,  -- empty: the engine's own
  synthesis_thinking INTEGER,                  -- empty: the engine's own
  protocol           TEXT    NOT NULL DEFAULT 'relay',
  created_at         TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agents (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  team_id       INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  name          TEXT    NOT NULL,
  system_prompt TEXT    NOT NULL,
  max_output_length_in_words INTEGER,
  context_window_in_tokens   INTEGER,      -- empty: the engine's own
  thinking      INTEGER,                   -- empty: the engine's own
  provider      TEXT    NOT NULL DEFAULT 'ollama',
  model         TEXT    NOT NULL,
  position      INTEGER NOT NULL,
  enabled       INTEGER NOT NULL DEFAULT 1,
  created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_agents_team ON agents(team_id, position);

CREATE TABLE IF NOT EXISTS sessions (
  id            TEXT    PRIMARY KEY,
  idea          TEXT    NOT NULL,
  team_id       INTEGER,                    -- deliberately no FK
  team_name     TEXT    NOT NULL,           -- denormalised
  max_rounds    INTEGER NOT NULL,
  team_snapshot TEXT    NOT NULL,           -- JSON: team + agents used in this run
  status        TEXT    NOT NULL,           -- running | done | error | stopped
  error         TEXT,
  created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
  finished_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at DESC);

-- One row per pass that changed team. Pass 1 is not written here: it is the
-- snapshot already frozen into `sessions`. A pass with no row of its own is
-- still being argued by whoever took over last.
CREATE TABLE IF NOT EXISTS session_passes (
  session_id    TEXT    NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  pass_no       INTEGER NOT NULL,
  team_id       INTEGER,                    -- deliberately no FK
  team_name     TEXT    NOT NULL,           -- denormalised
  team_snapshot TEXT    NOT NULL,           -- JSON: team + agents that took over
  created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (session_id, pass_no)
);

CREATE TABLE IF NOT EXISTS turns (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id     TEXT    NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  agent_id       INTEGER NOT NULL,          -- deliberately no FK
  agent_name     TEXT    NOT NULL,          -- denormalised
  agent_position INTEGER NOT NULL,
  pass_no        INTEGER NOT NULL DEFAULT 1,
  round          INTEGER NOT NULL,
  seq            INTEGER NOT NULL,
  kind           TEXT    NOT NULL DEFAULT 'agent',
  title          TEXT,
  text           TEXT    NOT NULL DEFAULT '',
  created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id, seq);
"""


# Columns added after the first release. `CREATE TABLE IF NOT EXISTS` leaves an
# existing table alone, so they have to be filled in by hand. Not a migration
# chain: just the few additions a database written by an older build is missing.
ADDED_COLUMNS = [
    ("turns", "pass_no", "INTEGER NOT NULL DEFAULT 1"),
    # Nullable on purpose: an empty cell means no length instruction at all,
    # which leaves prompts that state their own limit untouched.
    ("agents", "max_output_length_in_words", "INTEGER"),
    ("teams", "synthesis_max_output_length_in_words", "INTEGER"),
    # Everything written before LM Studio existed was running on Ollama.
    ("agents", "provider", "TEXT NOT NULL DEFAULT 'ollama'"),
    # Everything written before the swarm existed ran as a relay.
    ("teams", "protocol", "TEXT NOT NULL DEFAULT 'relay'"),
    # Nullable on purpose: empty keeps the old rule, the first agent's engine
    # and model, so no team written before this existed changes behaviour.
    ("teams", "synthesis_provider", "TEXT"),
    ("teams", "synthesis_model", "TEXT"),
    # Both nullable: empty keeps whatever the engine was configured with, so no
    # agent written before these existed changes behaviour.
    ("agents", "context_window_in_tokens", "INTEGER"),
    ("agents", "thinking", "INTEGER"),
    # The synthesis reads the whole transcript, so it needs its own window
    # rather than the one an agent picked for a one-line vote.
    ("teams", "synthesis_context_window_in_tokens", "INTEGER"),
    ("teams", "synthesis_thinking", "INTEGER"),
]


async def apply_schema(conn: aiosqlite.Connection) -> None:
    # SQLite disables foreign keys by default and the pragma is per connection:
    # without it, ON DELETE CASCADE does nothing at all.
    await conn.execute("PRAGMA foreign_keys = ON")
    await conn.executescript(SCHEMA)
    await _add_missing_columns(conn)
    await conn.commit()


async def _add_missing_columns(conn: aiosqlite.Connection) -> None:
    for table, column, definition in ADDED_COLUMNS:
        if column not in await _columns(conn, table):
            await conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


async def _columns(conn: aiosqlite.Connection, table: str) -> set[str]:
    async with conn.execute(f"PRAGMA table_info({table})") as cursor:
        return {row[1] for row in await cursor.fetchall()}
