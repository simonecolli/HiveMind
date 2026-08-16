# Documentation

One file per area of the system. Each explains not just what is there but why it
was built that way, including the decisions that were reversed and the limits
still open.

The root [README](../README.md) is the short version: what HiveMind does and how
to run it. Start here when you want to change something.

| File | Covers | Read it when |
| :--- | :--- | :--- |
| [backend.md](backend.md) | Layout, per-session graph compilation, dependency injection, streaming, stopping, tests | You are changing how a debate runs |
| [frontend.md](frontend.md) | Feature structure, what the canvas deliberately does not decide, the streaming hook | You are changing the interface |
| [storage.md](storage.md) | The two SQLite files, idempotent schema, snapshots, what is recomputed instead of stored | You are adding a column or wondering where something is kept |
| [teams.md](teams.md) | Agent and team fields, the rules appended to every prompt, the synthesis model, import/export | You are writing a team or adding a setting |
| [protocols.md](protocols.md) | Relay and swarm, worked through with three agents, how each is drawn, handover between teams | You are deciding how a team should argue |
| [providers.md](providers.md) | Ollama and LM Studio, environment variables, titles, reaching the engines from containers | You are configuring engines or debugging a connection |

## Suggested order

Reading them front to back is more than most changes need. For a first pass at
the whole system: **protocols** for the idea, **backend** for how it is
executed, **storage** for what survives.

For a change to a team or a prompt, **teams** on its own is enough - nothing in
it requires touching code.
