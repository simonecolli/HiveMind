import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router';
import { Plus, Square } from 'lucide-react';

import { api } from '../shared/api/client';
import { useAsync } from '../shared/api/useAsync';
import { ICON } from '../shared/icons';
import { Button, Notice } from '../shared/components/ui';
import { DebateCanvas } from '../canvas/DebateCanvas';
import { FollowUpComposer } from './FollowUpComposer';
import { Transcript } from './Transcript';
import { useDebateStream, type StreamTurn } from './useDebateStream';

const STATUS_LABEL = {
  connecting: 'Connecting...',
  running: 'Running',
  done: 'Finished',
  stopped: 'Stopped',
  error: 'Failed',
} as const;

export function SessionPage() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [stopping, setStopping] = useState(false);

  const { data: session, error, loading, reload } = useAsync(
    () => api.session(sessionId!),
    [sessionId],
  );

  // A finished debate is read back from the database; only a running one opens
  // the stream.
  const live = useDebateStream(session?.status === 'running' ? sessionId : undefined);

  // Once a pass ends, reload so the stored turns and the status catch up.
  useEffect(() => {
    if (live.active && live.status !== 'connecting' && live.status !== 'running') reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [live.active, live.status]);

  async function stop() {
    setStopping(true);
    try {
      await api.stopSession(session!.id);
    } finally {
      setStopping(false);
    }
  }

  const turns: StreamTurn[] = useMemo(() => {
    const stored: StreamTurn[] = (session?.turns ?? []).map((t) => ({ ...t, streaming: false }));
    if (!live.active) return stored;
    // The live stream only carries the pass in flight, so it is merged on top
    // of the stored turns rather than replacing them.
    const byId = new Map(stored.map((t) => [t.id, t]));
    for (const turn of live.turns) byId.set(turn.id, turn);
    return [...byId.values()].sort((a, b) => a.seq - b.seq);
  }, [session, live.active, live.turns]);

  if (loading && !session) {
    return <p className="p-10 text-sm text-faint">Loading...</p>;
  }
  if (error || !session) {
    return (
      <div className="p-10">
        <Notice>{error ?? 'Session not found'}</Notice>
      </div>
    );
  }

  const canvas = live.active && live.canvas ? live.canvas : session.canvas;
  const status = live.active ? live.status : session.status;
  const failure = live.error ?? session.error;
  const idle = status === 'done' || status === 'error' || status === 'stopped';

  // A session can change hands partway through. The last team to take it is the
  // one still holding the floor, and the chain is worth showing: it is the
  // difference between one debate and a relay of two.
  const passes = session.passes ?? [];
  const currentTeam = passes[passes.length - 1]?.team_name ?? session.team_name;
  const lineage = passes.length > 1 ? passes.map((p) => p.team_name).join(' -> ') : currentTeam;

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-start justify-between gap-6 border-b border-line px-8 py-5">
        <div className="min-w-0">
          <p className="edge-mark mb-1.5 text-signal">
            {lineage} -{' '}
            {/* Dropped once the session has changed hands: the figure describes
                the pass it opened with, not the one another team then ran. */}
            {passes.length <= 1 && (
              <>
                {session.max_rounds} {session.max_rounds === 1 ? 'round' : 'rounds'} -{' '}
              </>
            )}
            {STATUS_LABEL[status as keyof typeof STATUS_LABEL] ?? status}
            {status === 'running' && <span className="caret ml-1" />}
          </p>
          <h1 className="truncate font-read text-xl text-paper" title={session.idea}>
            {session.idea}
          </h1>
        </div>
        <div className="flex shrink-0 gap-2">
          {status === 'running' && (
            <Button variant="danger" onClick={stop} disabled={stopping}>
              <Square {...ICON} />
              {stopping ? 'Stopping...' : 'Stop'}
            </Button>
          )}
          <Button variant="ghost" onClick={() => navigate('/chat')}>
            <Plus {...ICON} />
            New idea
          </Button>
        </div>
      </header>

      {failure && (
        <div className="border-b border-line px-8 py-3">
          <Notice>{failure}</Notice>
        </div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,7fr)_minmax(0,8fr)]">
        <section className="flex min-h-0 flex-col border-r border-line">
          <div className="min-h-0 flex-1">
            {turns.length === 0 ? (
              <p className="px-8 py-6 text-sm text-faint">The first agent is taking the floor...</p>
            ) : (
              <Transcript turns={turns} selectedId={selectedId} onSelect={setSelectedId} />
            )}
          </div>

          {idle && (
            <FollowUpComposer
              sessionId={session.id}
              defaultRounds={session.max_rounds}
              currentTeam={currentTeam}
              onSent={reload}
            />
          )}
        </section>

        <section className="min-h-0">
          <DebateCanvas
            canvas={canvas}
            turns={turns}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        </section>
      </div>
    </div>
  );
}
