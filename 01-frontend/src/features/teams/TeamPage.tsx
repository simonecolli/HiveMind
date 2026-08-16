import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router';
import { ArrowDown, ArrowLeft, ArrowUp, Download, Plus, Trash2 } from 'lucide-react';

import { ApiError, api } from '../shared/api/client';
import type { TeamPayload } from '../shared/api/types';
import { useAsync } from '../shared/api/useAsync';
import { Page } from '../shared/components/Layout';

import { ICON } from '../shared/icons';
import {
  AgentDot,
  Button,
  Empty,
  IconButton,
  Notice,
  PageHeader,
  Panel,
} from '../shared/components/ui';
import { TeamFields } from './TeamFields';
import { TeamFlowPreview } from './TeamFlowPreview';
import { downloadTeam } from './teamFile';

export function TeamPage() {
  const { teamId } = useParams();
  const navigate = useNavigate();
  const id = Number(teamId);
  const { data: team, error, loading, reload } = useAsync(() => api.team(id), [id]);

  const [draft, setDraft] = useState<TeamPayload | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (team) {
      setDraft({
        name: team.name,
        description: team.description,
        protocol: team.protocol,
        default_max_rounds: team.default_max_rounds,
        synthesis_prompt: team.synthesis_prompt,
        synthesis_max_output_length_in_words: team.synthesis_max_output_length_in_words,
        synthesis_provider: team.synthesis_provider,
        synthesis_model: team.synthesis_model,
        synthesis_context_window_in_tokens: team.synthesis_context_window_in_tokens,
        synthesis_thinking: team.synthesis_thinking,
      });
    }
  }, [team]);

  async function saveTeam() {
    if (!draft) return;
    setSaveError(null);
    try {
      await api.updateTeam(id, draft);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      reload();
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : String(err));
    }
  }

  async function removeTeam() {
    await api.deleteTeam(id);
    navigate('/teams');
  }

  async function download() {
    setSaveError(null);
    try {
      downloadTeam(await api.exportTeam(id));
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : String(err));
    }
  }

  async function move(agentId: number, delta: number) {
    if (!team) return;
    const ids = team.agents.map((a) => a.id);
    const from = ids.indexOf(agentId);
    const to = from + delta;
    if (to < 0 || to >= ids.length) return;
    [ids[from], ids[to]] = [ids[to], ids[from]];
    await api.reorderAgents(id, ids);
    reload();
  }

  if (loading) return <Page><p className="text-sm text-faint">Loading...</p></Page>;
  if (error || !team) return <Page><Notice>{error ?? 'Team not found'}</Notice></Page>;

  return (
    <Page>
      <PageHeader
        overline="Teams"
        title={team.name}
        actions={
          <>
            <Button variant="ghost" onClick={() => navigate('/teams')}>
              <ArrowLeft {...ICON} />
              Back
            </Button>
            <Button variant="ghost" onClick={download}>
              <Download {...ICON} />
              Download team
            </Button>
            <Button variant="danger" onClick={removeTeam}>
              <Trash2 {...ICON} />
              Delete team
            </Button>
          </>
        }
      />

      <section className="mb-10">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="edge-mark text-faint">Settings</h2>
          <div className="flex items-center gap-3">
            {saved && <span className="text-xs text-sky">Saved</span>}
            <Button variant="ghost" onClick={saveTeam}>
              Save settings
            </Button>
          </div>
        </div>
        {saveError && (
          <div className="mb-4">
            <Notice>{saveError}</Notice>
          </div>
        )}
        <Panel className="p-5">{draft && (
            <TeamFields
              value={draft}
              onChange={setDraft}
              inheritedProvider={team?.agents[0]?.provider}
            />
          )}</Panel>
      </section>

      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="edge-mark text-faint">
            Agents -{' '}
            {(draft?.protocol ?? team.protocol) === 'swarm'
              ? 'all speak together'
              : 'in speaking order'}
          </h2>
          <Button onClick={() => navigate(`/teams/${id}/agents/new`)}>
            <Plus {...ICON} />
            Add agent
          </Button>
        </div>

        <div className="mb-6">
          <TeamFlowPreview
            teamId={id}
            agents={team.agents}
            rounds={draft?.default_max_rounds ?? team.default_max_rounds}
            protocol={draft?.protocol ?? team.protocol}
          />
        </div>

        {team.agents.length === 0 && (
          <Empty>No agents yet. The team cannot debate until you add one.</Empty>
        )}

        <ul className="divide-y divide-line border-y border-line">
          {team.agents.map((agent, index) => (
            <li key={agent.id} className="group flex items-center gap-3">
              <span className="edge-mark w-6 shrink-0 text-faint">{index + 1}</span>
              <AgentDot position={agent.position} />
              <button
                onClick={() => navigate(`/teams/${id}/agents/${agent.id}`)}
                className="min-w-0 flex-1 cursor-pointer py-4 text-left"
              >
                <p className="truncate text-paper transition-colors group-hover:text-signal">
                  {agent.name}
                  {!agent.enabled && <span className="edge-mark ml-2 text-faint">disabled</span>}
                </p>
                <p className="mt-1 truncate font-mono text-xs text-faint">
                  {agent.provider} - {agent.model}
                </p>
              </button>
              <div className="flex shrink-0 gap-1">
                <IconButton
                  onClick={() => move(agent.id, -1)}
                  disabled={index === 0}
                  aria-label={`Move ${agent.name} up`}
                >
                  <ArrowUp {...ICON} />
                </IconButton>
                <IconButton
                  onClick={() => move(agent.id, 1)}
                  disabled={index === team.agents.length - 1}
                  aria-label={`Move ${agent.name} down`}
                >
                  <ArrowDown {...ICON} />
                </IconButton>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </Page>
  );
}
