import { useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router';
import { Plus, Square, TriangleAlert } from 'lucide-react';

import { api } from '../shared/api/client';
import { useAsync } from '../shared/api/useAsync';
import { Page } from '../shared/components/Layout';

import { ICON } from '../shared/icons';
import { Button, Empty, Notice, Panel, PageHeader } from '../shared/components/ui';

const STATUS = {
  running: { label: 'running', tint: 'text-signal' },
  done: { label: 'finished', tint: 'text-faint' },
  stopped: { label: 'stopped by you', tint: 'text-muted' },
  error: { label: 'failed', tint: 'text-alert' },
} as const;

const RECENT = 5;
/** The shortlist: the teams you actually reach for, not the whole directory. */
const TOP_TEAMS = 5;
/** A panel holds this many rows; past it the list continues in the next panel. */
const PER_PANEL = 5;

function inPanels<T>(items: T[]): T[][] {
  const panels: T[][] = [];
  for (let i = 0; i < items.length; i += PER_PANEL) panels.push(items.slice(i, i + PER_PANEL));
  return panels;
}

/** "6-7 of 9", so a continued panel says where you are without a heading. */
const range = (index: number, panel: unknown[], total: number) => {
  const first = index * PER_PANEL + 1;
  const last = first + panel.length - 1;
  return `${first === last ? first : `${first}-${last}`} of ${total}`;
};

/** One cell of the grid. The panel is what keeps two columns of hairline rules
 * from reading as a single confused list. */
function Card({
  title,
  aside,
  className = '',
  children,
}: {
  title: string;
  aside?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    // `min-w-0`: a grid item defaults to min-width:auto, so without it the
    // truncating text inside widens the cell instead of shortening itself, and
    // the whole page picks up a horizontal scrollbar.
    <Panel className={`flex min-w-0 flex-col p-5 ${className}`}>
      <div className="mb-3 flex items-baseline justify-between gap-4">
        <h2 className="edge-mark text-faint">{title}</h2>
        {aside && <span className="text-xs text-faint">{aside}</span>}
      </div>
      {children}
    </Panel>
  );
}

export function DashboardPage() {
  const navigate = useNavigate();
  const [stopping, setStopping] = useState<string | null>(null);

  const { data, error, loading } = useAsync(() => api.dashboard(), []);
  const { data: sessions, reload: reloadSessions } = useAsync(() => api.sessions(), []);

  async function stop(id: string) {
    setStopping(id);
    try {
      await api.stopSession(id);
      reloadSessions();
    } finally {
      setStopping(null);
    }
  }

  const recent = sessions?.slice(0, RECENT) ?? [];
  const blocked = data?.teams.filter((t) => !t.ready) ?? [];

  return (
    <Page>
      <PageHeader
        overline="Dashboard"
        title="The hive"
        actions={
          <Button onClick={() => navigate('/chat')}>
            <Plus {...ICON} />
            New debate
          </Button>
        }
      />

      {error && <Notice>{error}</Notice>}
      {loading && !data && <p className="text-sm text-faint">Loading...</p>}

      {data && (
        // Readiness down the left, dependencies down the right, the debates full
        // width underneath where their sentences have room not to be truncated.
        // `dense` matters once readiness runs to a second panel: placement does
        // not backtrack, so without it the right column would start a row late
        // and leave a hole at the top.
        <div className="grid items-start gap-5 lg:grid-flow-row-dense lg:grid-cols-[3fr_2fr]">
          {data.teams.length === 0 ? (
            <Card title="Can I start" className="lg:col-start-1">
              <Empty>No teams yet. Build one from Teams.</Empty>
            </Card>
          ) : (
            <Card
              title="Can I start"
              className="lg:col-start-1"
              aside={
                data.teams.length > TOP_TEAMS
                  ? `${TOP_TEAMS} most used of ${data.teams.length}`
                  : blocked.length === 0
                    ? `${data.teams.length} ${data.teams.length === 1 ? 'team' : 'teams'}, all ready`
                    : `${blocked.length} of ${data.teams.length} blocked`
              }
            >
              <ul className="divide-y divide-line border-t border-line">
                {data.teams.slice(0, TOP_TEAMS).map((team) => (
                  <li key={team.id} className="group flex items-start gap-3 py-3">
                    <span
                      aria-hidden
                      className={`mt-1.5 size-1.5 shrink-0 rounded-full ${
                        team.ready ? 'bg-signal' : 'bg-alert'
                      }`}
                    />
                    <button
                      onClick={() => navigate(`/teams/${team.id}`)}
                      className="min-w-0 flex-1 cursor-pointer text-left"
                    >
                      <p className="truncate text-sm text-paper transition-colors group-hover:text-signal">
                        {team.name}
                      </p>
                      <p className="edge-mark mt-1 text-faint">
                        {team.protocol} - {team.agents}{' '}
                        {team.agents === 1 ? 'agent' : 'agents'} -{' '}
                        {/* The reason this one is on the list at all. */}
                        {team.debates === 0
                          ? 'never run'
                          : `${team.debates} ${team.debates === 1 ? 'debate' : 'debates'}`}
                      </p>
                      {/* Grouped by cause, not by agent: three agents on one
                          dead engine are a single thing to go and fix. */}
                      {team.blockers.map((blocker) => (
                        <p
                          key={blocker}
                          className="mt-1.5 flex items-start gap-1.5 text-xs text-alert"
                        >
                          <TriangleAlert {...ICON} className="mt-px shrink-0" />
                          {blocker}
                        </p>
                      ))}
                    </button>
                  </li>
                ))}
              </ul>
              {data.teams.length > TOP_TEAMS && (
                <button
                  onClick={() => navigate('/teams')}
                  className="mt-3 cursor-pointer self-start text-xs text-faint transition-colors hover:text-signal"
                >
                  The other {data.teams.length - TOP_TEAMS} in Teams
                </button>
              )}
            </Card>
          )}

          {data.models.length === 0 ? (
            <Card title="What you depend on" className="lg:col-start-2">
              <Empty>Models appear here once your agents name them.</Empty>
            </Card>
          ) : (
            inPanels(data.models).map((panel, index) => (
              <Card
                key={`models-${index}`}
                title="What you depend on"
                className="lg:col-start-2"
                aside={
                  data.models.length > PER_PANEL
                    ? range(index, panel, data.models.length)
                    : 'by agents that need it'
                }
              >
                <ul className="space-y-4 border-t border-line pt-4">
                  {panel.map((entry) => (
                    <li key={`${entry.provider}:${entry.model}`} className="min-w-0">
                      {/* The name gets its own line: LM Studio's are long, and
                          truncating the one identifier that matters here
                          defeats the point of the list. */}
                      <div className="flex items-baseline justify-between gap-3">
                        <p className="truncate font-mono text-sm text-paper">{entry.model}</p>
                        <span className="shrink-0 text-xs text-muted tabular-nums">
                          {entry.agents}
                        </span>
                      </div>

                      {/* Bars are relative to the heaviest dependency overall,
                          not to the heaviest on this panel: a bar has to mean
                          the same thing in the second panel as in the first. */}
                      <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-sm bg-line">
                        <div
                          className={`h-full rounded-sm ${
                            entry.installed ? 'bg-signal' : 'bg-alert'
                          }`}
                          style={{
                            width: `${Math.max(
                              4,
                              (entry.agents / data.models[0].agents) * 100,
                            )}%`,
                          }}
                        />
                      </div>

                      <p className="edge-mark mt-1.5 text-faint">
                        {entry.label} - {entry.teams} {entry.teams === 1 ? 'team' : 'teams'}
                        {/* Colour alone would not say it. */}
                        {!entry.installed && <span className="text-alert"> - offline</span>}
                      </p>
                    </li>
                  ))}
                </ul>
                {index === inPanels(data.models).length - 1 && (
                  <p className="mt-4 text-xs text-faint">
                    Bars are agents depending on each model, against the heaviest - not how
                    often it has run.
                  </p>
                )}
              </Card>
            ))
          )}

          <Card title="Where you left off" className="lg:col-span-2">
            {recent.length === 0 ? (
              <Empty>No debates yet. Start one from Chat.</Empty>
            ) : (
              <ul className="divide-y divide-line border-t border-line">
                {recent.map((session) => (
                  <li key={session.id} className="group flex items-center gap-4">
                    <button
                      onClick={() => navigate(`/chat/${session.id}`)}
                      className="min-w-0 flex-1 cursor-pointer py-3 text-left"
                    >
                      <p className="truncate font-read text-sm text-paper transition-colors group-hover:text-signal">
                        {session.idea}
                      </p>
                      <p className="edge-mark mt-1 text-faint">
                        {session.team_name} -{' '}
                        {session.created_at.slice(0, 16).replace('T', ' ')} -{' '}
                        <span className={STATUS[session.status].tint}>
                          {STATUS[session.status].label}
                        </span>
                      </p>
                    </button>
                    {/* A backend restart leaves a session saying `running` with
                        nothing left to finish it. This is the way out. */}
                    {session.status === 'running' && (
                      <Button
                        variant="danger"
                        className="shrink-0"
                        onClick={() => stop(session.id)}
                        disabled={stopping === session.id}
                      >
                        <Square {...ICON} />
                        {stopping === session.id ? 'Stopping...' : 'Stop'}
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}
    </Page>
  );
}
