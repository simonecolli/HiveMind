"""What a single turn asks of the engine.

An object rather than a growing list of arguments: these settings travel from
the agent record, through the graph node, to whichever provider serves it, and
every one of them would otherwise be another positional parameter in four
signatures and every test fake.

`None` always means "leave it to the engine", never "unbounded" - the provider
substitutes its own default, which for the output ceiling is a real number.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ChatOptions:
    # Hard ceiling on the generation, derived from the agent's word limit.
    max_tokens: int | None = None
    # How much of the debate the model is given to read. Left unset, the engine
    # decides - and its default is usually far smaller than the model allows.
    context_window: int | None = None
    # Whether the model is allowed to deliberate before answering.
    thinking: bool | None = None
