# Backend

FastAPI over LangGraph, Python 3.13, dependencies managed by `uv`.

## Layout

```
00-backend/
  main.py           entrypoint: wires settings, engines and the database
  src/
    config.py       Settings, entirely driven by environment variables
    app.py          app factory and dependency container
    routes/         HTTP surface: teams, agents, sessions, system
    graph/          the debate itself: builder, nodes, state, layout
    llm/            engine adapters and the turn titler
    db/             one repository per table, plus snapshot and transfer
  tests/            234 tests, no network and no database file required
```

## The graph is compiled per session, not at startup

`build_graph(team, agents, deps)` runs at the start of every debate. That is the
reason an agent added from the UI joins the next debate with no restart and no
code change: an agent is a row, and the graph is rebuilt from the rows.

Node names are `agent_{id}` because `:` is reserved in LangGraph.

## Dependency injection

`DebateDeps` carries the model factory, the titler, the turn recorder, the event
emitter and a stop predicate. Tests pass fakes for all five, which is why the
suite needs neither a running engine nor a database file and finishes in about
two seconds.

## Streaming

A debate runs as an asyncio task writing into a `Run` buffer, and clients
subscribe to that buffer over server-sent events. The buffer exists because the
frontend issues the POST and only then opens the stream - without it the first
events would be lost. It also lets a client attach to a debate that has already
finished, and reconnect to one still in flight.

## Stopping

Cooperative, not cancellation: nodes check a predicate between tokens. Whatever
was already written stays written, since the reader watched it appear, but a
turn stopped before its first token is discarded rather than left as an empty
bubble in the transcript. `stopped` is deliberately a separate status from
`error` - asking a debate to halt is not a failure.

## Errors

Engine problems are caught before the first token: starting a session validates
that every enabled agent's engine is up and holds the model it asks for, and
answers `503` or `422` naming the agent and the model. Failing halfway through a
twenty-agent swarm would be the alternative.

## Bounded turns

A word limit in a prompt is a request, and a model may ignore it: one answered a
60-word brief by generating past 7900 tokens and climbing, leaving a debate that
would never end. Two things stop that now.

Every turn carries a hard `num_predict` derived from the agent's word limit,
with generous headroom - the cap exists to stop a runaway, not to enforce a
length the prompt already asked for. An agent that names no limit falls back to
the engine's own ceiling (`HIVEMIND_MAX_OUTPUT_TOKENS`, 1024 by default), so
nothing is ever unbounded.

The cap alone was not enough. A thinking model spent the entire budget
deliberating and emitted nothing at all: reasoning never reaches `content`, so
the turn arrived empty and stopped on `done_reason=length`. Thinking is
therefore off by default (`reasoning=False`), which also keeps deliberation out
of the transcript and out of the countable tags some teams rely on. Set
`HIVEMIND_OLLAMA_THINKING=true` to restore it.

## Context window

Set per agent, in tokens, and left empty it is the engine's own. Measured rather
than assumed: Ollama loaded `qwen3.5:4b` at 32768 tokens when asked for nothing,
so the default is generous and a debate is not quietly truncated. What the
setting buys is the other direction - the same model held 4.2 GB at 32768 and
3.4 GB at 8192, which is what decides whether a swarm keeps two models resident
or thrashes between them. Ten personas voting in one line have no use for a
window their transcript will never fill.

## Tests

```bash
cd 00-backend && uv run pytest
```

Written test-first. `filterwarnings = ["error"]` in `pyproject.toml`, so a
deprecation in a dependency fails the suite rather than accumulating quietly.
