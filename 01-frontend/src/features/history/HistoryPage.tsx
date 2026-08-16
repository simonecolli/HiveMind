import { useNavigate } from 'react-router';
import { Trash2 } from 'lucide-react';

import { api } from '../shared/api/client';
import { useAsync } from '../shared/api/useAsync';
import { Page } from '../shared/components/Layout';

import { ICON } from '../shared/icons';
import { Button, Empty, Notice, PageHeader } from '../shared/components/ui';

const STATUS = {
  running: { label: 'running', tint: 'text-signal' },
  done: { label: 'finished', tint: 'text-faint' },
  stopped: { label: 'stopped by you', tint: 'text-muted' },
  error: { label: 'failed', tint: 'text-alert' },
} as const;

export function HistoryPage() {
  const navigate = useNavigate();
  const { data: sessions, error, loading, reload } = useAsync(() => api.sessions(), []);

  async function remove(id: string) {
    await api.deleteSession(id);
    reload();
  }

  return (
    <Page>
      <PageHeader overline="History" title="Past debates" />

      {error && <Notice>{error}</Notice>}
      {loading && <p className="text-sm text-faint">Loading...</p>}
      {sessions?.length === 0 && <Empty>No debates yet. Start one from Chat.</Empty>}

      <ul className="divide-y divide-line border-y border-line">
        {sessions?.map((session) => (
          <li key={session.id} className="group flex items-center gap-4">
            <button
              onClick={() => navigate(`/chat/${session.id}`)}
              className="min-w-0 flex-1 cursor-pointer py-4 text-left"
            >
              <p className="truncate font-read text-paper transition-colors group-hover:text-signal">
                {session.idea}
              </p>
              <p className="edge-mark mt-1.5 text-faint">
                {session.team_name} - {session.created_at.slice(0, 16).replace('T', ' ')} -{' '}
                <span className={STATUS[session.status].tint}>
                  {STATUS[session.status].label}
                </span>
              </p>
            </button>
            <Button variant="danger" className="shrink-0" onClick={() => remove(session.id)}>
              <Trash2 {...ICON} />
              Delete
            </Button>
          </li>
        ))}
      </ul>
    </Page>
  );
}
