"""Domain models and API payloads."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# How a round is run: one after another, or all at once then confront.
DebateProtocol = Literal["relay", "swarm"]

TurnKind = Literal["agent", "synthesis", "message"]


class TeamCreate(BaseModel):
    name: str = Field(min_length=1)
    synthesis_prompt: str = Field(min_length=1)
    description: str | None = None
    default_max_rounds: int = Field(default=2, ge=1, le=10)
    synthesis_max_output_length_in_words: int | None = Field(default=None, ge=1)
    synthesis_provider: str | None = Field(default=None, min_length=1)
    synthesis_model: str | None = Field(default=None, min_length=1)
    synthesis_context_window_in_tokens: int | None = Field(default=None, ge=256)
    synthesis_thinking: bool | None = None
    protocol: DebateProtocol = "relay"


class TeamUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    synthesis_prompt: str | None = Field(default=None, min_length=1)
    description: str | None = None
    default_max_rounds: int | None = Field(default=None, ge=1, le=10)
    synthesis_max_output_length_in_words: int | None = Field(default=None, ge=1)
    synthesis_provider: str | None = Field(default=None, min_length=1)
    synthesis_model: str | None = Field(default=None, min_length=1)
    synthesis_context_window_in_tokens: int | None = Field(default=None, ge=256)
    synthesis_thinking: bool | None = None
    protocol: DebateProtocol | None = None


class Team(BaseModel):
    id: int
    name: str
    description: str | None
    protocol: DebateProtocol = "relay"
    default_max_rounds: int
    synthesis_prompt: str
    synthesis_max_output_length_in_words: int | None = None
    # Empty means the synthesis runs on the first agent's engine and model.
    synthesis_provider: str | None = None
    synthesis_model: str | None = None
    synthesis_context_window_in_tokens: int | None = None
    synthesis_thinking: bool | None = None
    created_at: str
    updated_at: str


class AgentCreate(BaseModel):
    name: str = Field(min_length=1)
    system_prompt: str = Field(min_length=1)
    provider: str = Field(default="ollama", min_length=1)
    model: str = Field(min_length=1)
    max_output_length_in_words: int | None = Field(default=None, ge=1)
    context_window_in_tokens: int | None = Field(default=None, ge=256)
    thinking: bool | None = None
    enabled: bool = True


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    system_prompt: str | None = Field(default=None, min_length=1)
    max_output_length_in_words: int | None = Field(default=None, ge=1)
    context_window_in_tokens: int | None = Field(default=None, ge=256)
    thinking: bool | None = None
    provider: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    enabled: bool | None = None


class Agent(BaseModel):
    id: int
    team_id: int
    name: str
    system_prompt: str
    max_output_length_in_words: int | None
    # Empty means the engine's own setting, not a value we invented.
    context_window_in_tokens: int | None = None
    thinking: bool | None = None
    provider: str = "ollama"
    model: str
    position: int
    enabled: bool
    created_at: str
    updated_at: str


class Turn(BaseModel):
    """A single contribution to the debate.

    `agent_position` is copied from the agent when the turn starts: the layout
    needs it, and freezing it keeps reordering a team from moving the nodes of
    debates that already finished.
    """

    id: int
    agent_id: int
    agent_name: str
    agent_position: int
    # `pass` is a reserved word in Python, so the column is named `pass_no`
    # everywhere rather than being renamed only on this side.
    pass_no: int = 1
    round: int
    seq: int
    kind: TurnKind = "agent"
    title: str | None = None
    text: str = ""


# `stopped` is deliberately not `error`: asking a debate to halt is not a
# failure, and the history should not show it as one.
SessionStatus = Literal["running", "done", "error", "stopped"]


class SessionCreate(BaseModel):
    idea: str = Field(min_length=1)
    team_id: int | None
    team_name: str
    max_rounds: int = Field(ge=1, le=10)
    team_snapshot: dict


class Session(BaseModel):
    id: str
    idea: str
    team_id: int | None
    team_name: str
    max_rounds: int
    team_snapshot: dict
    status: SessionStatus
    error: str | None
    created_at: str
    finished_at: str | None


class SessionStart(BaseModel):
    """Request payload that kicks off a debate."""

    idea: str = Field(min_length=1)
    team_id: int
    max_rounds: int | None = Field(default=None, ge=1, le=10)


class SessionPass(BaseModel):
    """Which team argued a pass. Recorded only where it changes."""

    pass_no: int
    team_id: int | None
    team_name: str
    protocol: DebateProtocol = "relay"


class SessionMessage(BaseModel):
    """A follow-up that opens a further pass.

    Naming a team hands the session over to it: the thread, the canvas and the
    summaries carry on, argued by someone else. Left empty, the pass stays with
    whoever holds the floor.
    """

    text: str = Field(min_length=1)
    max_rounds: int | None = Field(default=None, ge=1, le=10)
    team_id: int | None = None

    @field_validator("text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("The message cannot be blank")
        return value.strip()


class CanvasNode(BaseModel):
    id: str
    type: str
    position: dict[str, float]
    data: dict


class CanvasEdge(BaseModel):
    id: str
    source: str
    target: str
    animated: bool = True


class Canvas(BaseModel):
    nodes: list[CanvasNode]
    edges: list[CanvasEdge]


class TeamDetail(Team):
    agents: list[Agent]


class AgentExport(BaseModel):
    name: str = Field(min_length=1)
    system_prompt: str = Field(min_length=1)
    provider: str = Field(default="ollama", min_length=1)
    model: str = Field(min_length=1)
    max_output_length_in_words: int | None = Field(default=None, ge=1)
    context_window_in_tokens: int | None = Field(default=None, ge=256)
    thinking: bool | None = None
    enabled: bool = True


class TeamExport(BaseModel):
    """Portable shape of a team.

    Ids and timestamps are left out on purpose: they mean nothing on another
    machine, and importing them would only invite collisions.
    """

    name: str = Field(min_length=1)
    synthesis_prompt: str = Field(min_length=1)
    description: str | None = None
    default_max_rounds: int = Field(default=2, ge=1, le=10)
    synthesis_max_output_length_in_words: int | None = Field(default=None, ge=1)
    synthesis_provider: str | None = Field(default=None, min_length=1)
    synthesis_model: str | None = Field(default=None, min_length=1)
    synthesis_context_window_in_tokens: int | None = Field(default=None, ge=256)
    synthesis_thinking: bool | None = None
    protocol: DebateProtocol = "relay"
    agents: list[AgentExport] = Field(default_factory=list)


class SessionDetail(Session):
    turns: list[Turn]
    canvas: Canvas
    passes: list[SessionPass] = Field(default_factory=list)


class ReorderRequest(BaseModel):
    ordered_ids: list[int]
