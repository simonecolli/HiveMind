# HiveMind

A local brainstorming arena. You give an idea to a team of AI agents with
different roles, they argue it out over several rounds, and you watch the
exchange build on a canvas as it is written. Everything runs on your own
hardware: no idea, no draft, no client detail ever leaves the machine.

*Example debate*
![A finished debate: five agents argue what HiveMind should add in v2 over three rounds, their turns readable on the left while the canvas holds every round on the right](docs/img/debate.png)

## What it does

**Teams you compose, not code you edit.** An agent is a row in SQLite - a name,
a system prompt, an engine, a model, a position. The debate graph is compiled at
the start of every session, so an agent added from the UI joins the next debate
with no restart and no code change.

**Two ways to run a round.** *Relay* sends the agents one after another, each
reading everyone before it. *Swarm* runs them all at once against the same
context, so nobody anchors on whoever spoke first, and they confront each other
from the next round on. A team picks one, and the editor draws the shape it
will run as you compose it.

*Swarm*
![The team editor's preview of a swarm: the idea fanning out to five named agents and back into a single synthesis, captioned "3 rounds, all at once"](docs/img/team-view.png)

**A conversation, not a one-shot.** When a debate ends you can send it back in
with a correction or a new constraint, and it opens another pass carrying the
previous summaries. That pass can also be handed to a **different team** - a
panel of personas votes, then a desk of professionals works from its verdict,
in one thread.

**Two engines, chosen per agent.** Ollama and LM Studio side by side, so quick
voices can sit on a small model while the judgements run on a larger one.

**Streamed and interruptible.** Turns arrive token by token over server-sent
events. A debate going nowhere can be stopped mid-sentence; what was already
written stays.

**Portable teams.** Export a team to JSON, import it back or somewhere else.
`examples/` ships ready-made ones in English and Italian, from a three-voice
think tank to a twenty-agent engineering org.

A dashboard on the landing page answers the two questions you have on opening
it: which teams could run right now, and which model would take the most of
them down with it.

## Requirements

[Ollama](https://ollama.com) or [LM Studio](https://lmstudio.ai), running
natively so inference keeps GPU acceleration, plus at least one model:

```bash
ollama pull qwen2.5:7b   # what the seeded team and the examples ask for
```

## Running it with Docker

The engines stay on the host - a container cannot reach the GPU - so they have
to be reachable from outside loopback:

```bash
./serve-ollama.sh          # binds 0.0.0.0 and tunes Ollama for swarms
docker compose up --build  # http://localhost:5173
```

In LM Studio, the equivalent is the "Serve on Local Network" toggle.

Ports are configurable if those are taken:

```bash
HIVEMIND_WEB_PORT=8080 HIVEMIND_BACKEND_PORT=8081 docker compose up
```

## Running it from source

```bash
cd 00-backend  && uv run main.py     # http://localhost:8000
cd 01-frontend && npm install && npm run dev   # http://localhost:5173
```

Requires Python 3.13 with [uv](https://docs.astral.sh/uv/), and Node 22.

## How it is built

| Layer | Choice | Role |
| :--- | :--- | :--- |
| Engines | Ollama, LM Studio | Run the models locally, per agent |
| Orchestrator | LangGraph + FastAPI | Builds the debate graph at runtime, streams it |
| Storage | SQLite x2 | Teams, agents, sessions and turns; graph checkpoints apart |
| Interface | React + React Flow | Composer, transcript, and the canvas |

The canvas is never authored by a model. Nodes, edges and coordinates are a
deterministic function of the turns, computed in Python, so a graph cannot come
out inconsistent - and it is recomputed rather than stored, so reopening a
session months later draws exactly what happened.

Deeper notes, one file per area - see [docs/](docs/README.md) for what to read
when:

- [Backend](docs/backend.md) - graph, streaming, dependency injection, tests
- [Frontend](docs/frontend.md) - structure and what the canvas does not decide
- [Database and storage](docs/storage.md) - schema, snapshots, what is not stored
- [Agents and teams](docs/teams.md) - configuration, shared rules, import/export
- [Protocols](docs/protocols.md) - relay and swarm, with an example
- [Providers](docs/providers.md) - engines, configuration, reaching them from containers

## Tests

```bash
cd 00-backend && uv run pytest      # 279 tests, ~2s
```

Backend written test-first, with fakes for the engines, the model, the turn
recorder and the event stream, so the suite needs neither a running model nor a
database file. The frontend has no tests by design: the logic worth testing
lives in the backend.

## Licence

MIT - see [LICENSE](LICENSE).
