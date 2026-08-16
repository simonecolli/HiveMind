import { useState } from 'react';
import { CornerDownLeft } from 'lucide-react';

import { ApiError, api } from '../shared/api/client';
import { useAsync } from '../shared/api/useAsync';
import { ICON } from '../shared/icons';
import { Button, Notice, Select, Textarea } from '../shared/components/ui';

/** Sends a further message into a finished debate, opening the next pass.
 *
 * The pass can also change hands: picking another team hands the thread over to
 * it, which is how a panel feeds a desk without copying its summary by hand.
 */
export function FollowUpComposer({
  sessionId,
  defaultRounds,
  currentTeam,
  onSent,
}: {
  sessionId: string;
  defaultRounds: number;
  currentTeam: string;
  onSent: () => void;
}) {
  const [text, setText] = useState('');
  const [rounds, setRounds] = useState<number | null>(null);
  const [teamId, setTeamId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  const { data: teams } = useAsync(() => api.teams(), []);

  async function send() {
    if (!text.trim()) return;
    setSending(true);
    setError(null);
    try {
      await api.sendMessage(sessionId, {
        text,
        ...(rounds ? { max_rounds: rounds } : {}),
        ...(teamId ? { team_id: teamId } : {}),
      });
      setText('');
      setRounds(null);
      setTeamId(null);
      onSent();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setSending(false);
    }
  }

  const handingOver = teamId !== null;

  return (
    <div className="border-t border-line bg-surface px-8 py-5">
      {error && (
        <div className="mb-3">
          <Notice>{error}</Notice>
        </div>
      )}

      <Textarea
        rows={3}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Send the board back in: a correction, a constraint, a new angle..."
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) void send();
        }}
      />

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <Button onClick={send} disabled={!text.trim() || sending}>
          <CornerDownLeft {...ICON} />
          {sending ? 'Sending...' : handingOver ? 'Hand over' : 'Send to the board'}
        </Button>

        <Select
          className="w-auto"
          value={teamId ?? ''}
          onChange={(e) => setTeamId(e.target.value ? Number(e.target.value) : null)}
          aria-label="Team for this pass"
        >
          <option value="">Stay with {currentTeam}</option>
          {(teams ?? []).map((team) => (
            <option key={team.id} value={team.id}>
              Hand over to {team.name}
            </option>
          ))}
        </Select>

        <Select
          className="w-auto"
          value={rounds ?? ''}
          onChange={(e) => setRounds(e.target.value ? Number(e.target.value) : null)}
          aria-label="Rounds for this message"
        >
          <option value="">
            {handingOver ? "That team's own rounds" : `Same rounds (${defaultRounds})`}
          </option>
          {[1, 2, 3, 4, 5].map((n) => (
            <option key={n} value={n}>
              {n} {n === 1 ? 'round' : 'rounds'}
            </option>
          ))}
        </Select>
      </div>
    </div>
  );
}
