/** Mirror of the backend Pydantic models (`00-backend/src/models.py`). */

export type TurnKind = 'agent' | 'synthesis' | 'message';
export type DebateProtocol = 'relay' | 'swarm';

export type SessionStatus = 'running' | 'done' | 'error' | 'stopped';

export interface Team {
  id: number;
  name: string;
  description: string | null;
  protocol: DebateProtocol;
  default_max_rounds: number;
  synthesis_prompt: string;
  synthesis_max_output_length_in_words: number | null;
  /** Empty means the synthesis runs on the first agent's engine and model. */
  synthesis_provider: string | null;
  synthesis_model: string | null;
  synthesis_context_window_in_tokens: number | null;
  synthesis_thinking: boolean | null;
  created_at: string;
  updated_at: string;
}

export interface Agent {
  id: number;
  team_id: number;
  name: string;
  system_prompt: string;
  max_output_length_in_words: number | null;
  /** Both empty mean the engine's own setting, not a value we invented. */
  context_window_in_tokens: number | null;
  thinking: boolean | null;
  provider: string;
  model: string;
  position: number;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface TeamDetail extends Team {
  agents: Agent[];
}

export interface Turn {
  id: number;
  agent_id: number;
  agent_name: string;
  agent_position: number;
  pass_no: number;
  round: number;
  seq: number;
  kind: TurnKind;
  title: string | null;
  text: string;
}

export interface CanvasNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: {
    label: string;
    agent_name?: string;
    round?: number;
    has_text?: boolean;
  };
}

export interface CanvasEdge {
  id: string;
  source: string;
  target: string;
  animated: boolean;
}

export interface Canvas {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
}

export interface Session {
  id: string;
  idea: string;
  team_id: number | null;
  team_name: string;
  max_rounds: number;
  status: SessionStatus;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

/** Which team argued a pass. Recorded only where it changes. */
export interface SessionPass {
  pass_no: number;
  team_id: number | null;
  team_name: string;
  protocol: DebateProtocol;
}

export interface SessionDetail extends Session {
  turns: Turn[];
  canvas: Canvas;
  passes: SessionPass[];
}

export interface TeamPayload {
  name: string;
  synthesis_prompt: string;
  description?: string | null;
  protocol?: DebateProtocol;
  default_max_rounds?: number;
  synthesis_max_output_length_in_words?: number | null;
  synthesis_provider?: string | null;
  synthesis_model?: string | null;
  synthesis_context_window_in_tokens?: number | null;
  synthesis_thinking?: boolean | null;
}

export interface AgentPayload {
  name: string;
  system_prompt: string;
  provider?: string;
  model: string;
  max_output_length_in_words?: number | null;
  context_window_in_tokens?: number | null;
  thinking?: boolean | null;
  enabled?: boolean;
}

/** Portable shape of a team: no ids, no timestamps. */
export interface TeamExport {
  name: string;
  synthesis_prompt: string;
  description: string | null;
  default_max_rounds: number;
  synthesis_max_output_length_in_words: number | null;
  synthesis_provider: string | null;
  synthesis_model: string | null;
  synthesis_context_window_in_tokens: number | null;
  synthesis_thinking: boolean | null;
  protocol: DebateProtocol;
  agents: {
    name: string;
    system_prompt: string;
    provider: string;
    model: string;
    max_output_length_in_words: number | null;
    context_window_in_tokens: number | null;
    thinking: boolean | null;
    enabled: boolean;
  }[];
}

/** One local engine and what it currently holds. */
export interface EngineCatalogue {
  provider: string;
  label: string;
  available: boolean;
  models: string[];
}

export interface EngineHealth {
  status: string;
  engines: { provider: string; label: string; available: boolean }[];
}

/** What the landing page needs: can I start, and what do I depend on. */
export interface TeamReadiness {
  id: number;
  name: string;
  protocol: DebateProtocol;
  agents: number;
  /** Debates this team argued, opened or handed to it. */
  debates: number;
  ready: boolean;
  /** Every reason this team would refuse to start, not only the first. */
  blockers: string[];
}

export interface ModelUsage {
  provider: string;
  label: string;
  model: string;
  agents: number;
  teams: number;
  installed: boolean;
}

export interface Dashboard {
  engines: EngineCatalogue[];
  teams: TeamReadiness[];
  models: ModelUsage[];
}
