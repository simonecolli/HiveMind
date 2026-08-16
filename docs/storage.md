# Database and storage

Two SQLite files under `data/`, both gitignored.

| File | Holds |
| :--- | :--- |
| `hivemind.db` | teams, agents, sessions, turns, handovers |
| `checkpoints.db` | LangGraph's own state snapshots |

They are kept apart because they have different lifetimes: the first is your
work and worth backing up, the second is engine bookkeeping and can be deleted
without losing a debate.

## Schema

Applied idempotently at startup - `CREATE TABLE IF NOT EXISTS`, plus an
`ADDED_COLUMNS` list for columns that arrived later and have to be added by hand
to a database written by an older build. There is no versioned migration chain:
while the project stays local and single-user, that would be more machinery than
the problem deserves. Every added column is nullable or carries a default, so an
older file keeps working untouched.

WAL is enabled, so readers and the writer stop blocking each other.

## Turns

A turn is one contribution: agent, pass, round, sequence, kind, title, text. The
user's follow-up messages are stored as turns too, with `kind = 'message'` -
that puts them in the transcript, on the canvas and in the ordering with no
special case anywhere.

`agent_position` is copied onto the turn when it starts rather than read from
the agent later, so reordering a team does not move the nodes of debates that
already finished.

## Snapshots

Starting a session freezes the team and its agents into the session row as JSON.
Follow-ups run from that snapshot, not from the live team, so editing a prompt
or deleting the team halfway cannot change who is arguing. A session that hands
over to another team freezes that one too, in `session_passes`.

## What is not stored

The canvas. Nodes, edges and coordinates are a deterministic function of the
turns, so they are recomputed on read instead of persisted and risking drift.
