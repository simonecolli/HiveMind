# Providers

Two local engines, chosen per agent. Nothing leaves the machine.

| Engine | Reached at | Client |
| :--- | :--- | :--- |
| Ollama | `/api/tags`, native API | `ChatOllama` |
| LM Studio | `/v1`, OpenAI-compatible | `ChatOpenAI`, with a dummy key |

The LM Studio key is required by the client and ignored by the server.

## Per agent, not per team

Each agent carries its own `provider` and `model`, so a team can put its quick
voices on a small model and its judgements on a larger one - or split across
both engines. The synthesis follows the first agent unless the team names its
own.

## Availability is checked up front

`GET /api/v1/models` returns each engine, whether it answers, and what it holds.
Starting a session validates every enabled agent against that catalogue and
refuses with `503` (engine down) or `422` (model missing), naming the agent and
the model. The alternative is discovering it on the last node of a long swarm.

## Configuration

Everything is an environment variable, read in `src/config.py`:

| Variable | Default |
| :--- | :--- |
| `HIVEMIND_OLLAMA_URL` | `http://localhost:11434` |
| `HIVEMIND_LMSTUDIO_URL` | `http://localhost:1234/v1` |
| `HIVEMIND_TITLE_PROVIDER` | `ollama` |
| `HIVEMIND_TITLE_MODEL` | `qwen2.5:7b` |
| `HIVEMIND_HOST` / `HIVEMIND_PORT` | `127.0.0.1` / `8000` |
| `HIVEMIND_MAX_OUTPUT_TOKENS` | `1024` |
| `HIVEMIND_OLLAMA_THINKING` | unset (thinking off) |
| `HIVEMIND_DATA_DIR` | `./data` |
| `HIVEMIND_CORS_ORIGINS` | `http://localhost:5173` |

## Thinking

Off by default. Left to the model, a thinking one spends its whole token budget
deliberating and emits nothing into `content`, so the turn arrives empty - and
where it does answer, the reasoning would land in the transcript and break the
countable tags some teams depend on.

An agent may override it either way; `HIVEMIND_OLLAMA_THINKING=true` moves the
default for agents that express no preference. Neither has an equivalent on the
LM Studio side, where thinking and context are set on the model as it is loaded.

## Titles

Each turn gets a short generated title so its node is readable at a glance. It
is one extra short call per turn, on the smallest model you have. If the model
will not cooperate the node falls back to agent and round, and the debate
carries on - a garnish must not be able to break a debate.

## Reaching the engines from containers

The engines stay on the host: they need the GPU, which a Linux container on
Apple Silicon cannot reach at all. Two things make the crossing work.

`ollama serve` binds loopback by default, which no container can reach. Bind it
to all interfaces - `OLLAMA_HOST=0.0.0.0:11434`, as `serve-ollama.sh` does. Note
this also exposes Ollama to your local network. In LM Studio the equivalent is
the "Serve on Local Network" toggle.

The containers then address the host as `host.docker.internal`, which compose
maps explicitly via `extra_hosts` so it works on Linux as well as on Docker
Desktop.
