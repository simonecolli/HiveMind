import type {
  Agent,
  Dashboard,
  AgentPayload,
  Session,
  SessionDetail,
  EngineCatalogue,
  EngineHealth,
  Team,
  TeamDetail,
  TeamExport,
  TeamPayload,
} from './types';

const BASE = '/api/v1';

export class ApiError extends Error {
  // An explicit field rather than a parameter property: `erasableSyntaxOnly`
  // forbids syntax that would require emitted code.
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { 'content-type': 'application/json', ...init?.headers },
    });
  } catch {
    throw new ApiError(0, 'The backend is not responding. Start it with `uv run main.py`.');
  }

  if (!response.ok) {
    throw new ApiError(response.status, await readError(response));
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === 'string') return body.detail;
    if (Array.isArray(body?.detail)) {
      // FastAPI validation errors: field + reason.
      return body.detail
        .map((d: { loc?: string[]; msg?: string }) => `${d.loc?.slice(-1)}: ${d.msg}`)
        .join('; ');
    }
  } catch {
    /* non-JSON body: the fallback is below */
  }
  return `Request failed (${response.status})`;
}

export const api = {
  health: () => request<EngineHealth>('/health'),
  models: () => request<EngineCatalogue[]>('/models'),
  dashboard: () => request<Dashboard>('/dashboard'),

  teams: () => request<Team[]>('/teams'),
  team: (id: number) => request<TeamDetail>(`/teams/${id}`),
  createTeam: (payload: TeamPayload) =>
    request<Team>('/teams', { method: 'POST', body: JSON.stringify(payload) }),
  updateTeam: (id: number, payload: Partial<TeamPayload>) =>
    request<Team>(`/teams/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deleteTeam: (id: number) => request<void>(`/teams/${id}`, { method: 'DELETE' }),
  duplicateTeam: (id: number) => request<Team>(`/teams/${id}/duplicate`, { method: 'POST' }),
  exportTeam: (id: number) => request<TeamExport>(`/teams/${id}/export`),
  importTeam: (payload: unknown) =>
    request<Team>('/teams/import', { method: 'POST', body: JSON.stringify(payload) }),

  addAgent: (teamId: number, payload: AgentPayload) =>
    request<Agent>(`/teams/${teamId}/agents`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  reorderAgents: (teamId: number, orderedIds: number[]) =>
    request<Agent[]>(`/teams/${teamId}/agents/reorder`, {
      method: 'POST',
      body: JSON.stringify({ ordered_ids: orderedIds }),
    }),
  updateAgent: (id: number, payload: Partial<AgentPayload>) =>
    request<Agent>(`/agents/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deleteAgent: (id: number) => request<void>(`/agents/${id}`, { method: 'DELETE' }),

  sessions: () => request<Session[]>('/sessions'),
  session: (id: string) => request<SessionDetail>(`/sessions/${id}`),
  startSession: (payload: { idea: string; team_id: number; max_rounds?: number }) =>
    request<{ session_id: string }>('/sessions', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  deleteSession: (id: string) => request<void>(`/sessions/${id}`, { method: 'DELETE' }),
  stopSession: (id: string) => request<void>(`/sessions/${id}/stop`, { method: 'POST' }),
  /** `team_id` hands the session over: the next pass is argued by that team. */
  sendMessage: (
    id: string,
    payload: { text: string; max_rounds?: number; team_id?: number },
  ) =>
    request<{ session_id: string }>(`/sessions/${id}/messages`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};
