# Agents and teams

An **agent** is a row: a name, a system prompt, an engine, a model, an optional
length limit, a position in the speaking order, and an on/off switch. A **team**
is an ordered set of agents plus its own preset - protocol, default rounds, and
the prompt that writes the final synthesis.

Adding an agent is an `INSERT`, not a code change. The graph is compiled at the
start of each session, so a new agent joins the next debate with no restart.

## Length belongs in a field, not in the prompt

`max_output_length_in_words` on the agent, `synthesis_max_output_length_in_words`
on the team. Left empty, no length sentence is added at all - so a prompt that
states its own limit is not contradicted by a second one appended underneath.

The same field also sets a hard token ceiling on the generation, with room to
spare, so a model that ignores the instruction is stopped rather than left to
run. An agent with no limit falls back to the engine's ceiling.

## Context window and thinking

Both per agent, both optional, both meaning "the engine's own" when left empty.

The window is measured in tokens of debate the agent is given to read. The
engine's default is generous, so this is mostly a memory lever: the same model
held 4.2 GB at 32768 tokens and 3.4 GB at 8192. A team of ten small voices and
two large judges fits differently depending on it.

Thinking is deliberation before answering. It never reaches the transcript, so
an agent left to think can spend its whole token budget and emit nothing at all
- which is exactly what one did. Off by default, per agent, overridable both
ways.

The synthesis has its own pair of the same settings on the team, and inherits
neither from the first agent. That is deliberate: it borrows that agent's model,
but it reads the entire transcript, so taking a window chosen for a one-line
vote would starve the one node that actually needs room.

## Rules every agent gets

Appended to each system prompt rather than pasted into every team's text, so
they cover the teams you already wrote and the ones you write later:

- **Language.** Answer in the language of the original idea, whatever language
  the surrounding instructions are written in. Without it a small model drifts,
  and not always towards English. Repeated at the end of the user message too,
  because that is the last thing the model reads and it weighs it most.
- **Length**, when the field is set.

## The synthesis model

`synthesis_provider` and `synthesis_model` on the team, both optional. Empty
means the synthesis runs on the first agent's engine and model, which is the
original behaviour. Naming one matters when the summary has to do work the
agents are too small for, or when the first position carries no meaning - in a
swarm, every agent runs at once, so "first" is just a row number.

## Import and export

```
GET  /api/v1/teams/{id}/export      ->  a portable JSON file
POST /api/v1/teams/import           <-  the same shape
```

Ids and timestamps are left out on purpose: they mean nothing on another machine
and would only invite collisions. A name that already exists is suffixed rather
than refused. Import is transactional - a failure halfway takes the freshly
created team down with it instead of leaving half a board behind.

The `examples/` directory holds ready-made teams in English and Italian, from a
three-voice think tank to a twenty-agent engineering org.
