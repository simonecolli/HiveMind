import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { Command, Play } from 'lucide-react';

import { ApiError, api } from '../shared/api/client';
import { useAsync } from '../shared/api/useAsync';
import { Page } from '../shared/components/Layout';

import { ICON } from '../shared/icons';
import {
  Button,
  Empty,
  Field,
  Notice,
  PageHeader,
  Select,
  Textarea,
} from '../shared/components/ui';

export function ChatPage() {
  const navigate = useNavigate();
  const { data: teams, loading } = useAsync(() => api.teams(), []);

  const [idea, setIdea] = useState('');
  const [teamId, setTeamId] = useState<number | null>(null);
  const [rounds, setRounds] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    if (teams?.length && teamId === null) setTeamId(teams[0].id);
  }, [teams, teamId]);

  const team = teams?.find((t) => t.id === teamId);

  async function start() {
    if (!teamId) return;
    setStarting(true);
    setError(null);
    try {
      const { session_id } = await api.startSession({
        idea,
        team_id: teamId,
        ...(rounds ? { max_rounds: rounds } : {}),
      });
      navigate(`/chat/${session_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
      setStarting(false);
    }
  }

  return (
    <Page>
      <PageHeader overline="Chat" title="Put an idea on the table" />

      {loading && <p className="text-sm text-faint">Loading...</p>}
      {teams?.length === 0 && (
        <Empty>No teams available. Create one under Teams before opening a debate.</Empty>
      )}

      {teams && teams.length > 0 && (
        <div className="space-y-5">
          <Field label="The idea" hint="Write it raw. The board needs material, not a report.">
            <Textarea
              rows={5}
              value={idea}
              onChange={(e) => setIdea(e.target.value)}
              placeholder="Write here your idea..."
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) start();
              }}
            />
          </Field>

          <div className="grid grid-cols-2 gap-5">
            <Field label="Team">
              <Select value={teamId ?? ''} onChange={(e) => setTeamId(Number(e.target.value))}>
                {teams.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </Select>
            </Field>

            <Field label="Rounds">
              <Select
                value={rounds ?? ''}
                onChange={(e) => setRounds(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Team default ({team?.default_max_rounds ?? 2})</option>
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </Select>
            </Field>
          </div>

          {error && <Notice>{error}</Notice>}

          <div className="flex items-center gap-4">
            <Button onClick={start} disabled={!idea.trim() || !teamId || starting}>
              <Play {...ICON} />
              {starting ? 'Calling the board...' : 'Start the debate'}
            </Button>
            <span className="edge-mark flex items-center gap-1 text-faint">
              <Command size={12} strokeWidth={1.75} aria-hidden /> + enter
            </span>
          </div>
        </div>
      )}
    </Page>
  );
}
