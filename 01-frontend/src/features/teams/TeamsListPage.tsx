import { useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { Copy, Plus, Upload } from 'lucide-react';

import { ApiError, api } from '../shared/api/client';
import { useAsync } from '../shared/api/useAsync';
import { Page } from '../shared/components/Layout';

import { ICON } from '../shared/icons';
import { Button, Empty, Notice, PageHeader } from '../shared/components/ui';
import { readTeamFile } from './teamFile';

export function TeamsListPage() {
  const navigate = useNavigate();
  const { data: teams, error, loading, reload } = useAsync(() => api.teams(), []);
  const fileInput = useRef<HTMLInputElement>(null);
  const [importError, setImportError] = useState<string | null>(null);

  async function duplicate(id: number) {
    await api.duplicateTeam(id);
    reload();
  }

  async function load(file: File | undefined) {
    if (!file) return;
    setImportError(null);
    try {
      const team = await api.importTeam(await readTeamFile(file));
      // Straight to the new team: it may have been renamed to avoid a clash.
      navigate(`/teams/${team.id}`);
    } catch (err) {
      setImportError(err instanceof ApiError || err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <Page>
      <PageHeader
        overline="Teams"
        title="Your boards"
        actions={
          <>
            <Button variant="ghost" onClick={() => fileInput.current?.click()}>
              <Upload {...ICON} />
              Load team
            </Button>
            <Button onClick={() => navigate('/teams/new')}>
              <Plus {...ICON} />
              Add team
            </Button>
          </>
        }
      />

      <input
        ref={fileInput}
        type="file"
        accept="application/json,.json"
        className="hidden"
        onChange={(e) => {
          void load(e.target.files?.[0]);
          // Reset, so picking the same file twice fires the change event again.
          e.target.value = '';
        }}
      />

      {importError && (
        <div className="mb-5">
          <Notice>{importError}</Notice>
        </div>
      )}
      {error && <Notice>{error}</Notice>}
      {loading && <p className="text-sm text-faint">Loading...</p>}

      {teams?.length === 0 && <Empty>No teams yet. Create one to start a debate.</Empty>}

      <ul className="divide-y divide-line border-y border-line">
        {teams?.map((team) => (
          <li key={team.id} className="group flex items-center gap-4">
            <button
              onClick={() => navigate(`/teams/${team.id}`)}
              className="min-w-0 flex-1 cursor-pointer py-4 text-left"
            >
              <p className="truncate text-paper transition-colors group-hover:text-signal">
                {team.name}
              </p>
              <p className="mt-1 truncate text-xs text-faint">
                {team.description || 'No description'}
              </p>
            </button>
            <span className="edge-mark shrink-0 text-faint">
              {team.default_max_rounds} {team.default_max_rounds === 1 ? 'round' : 'rounds'}
            </span>
            <Button
              variant="ghost"
              className="shrink-0"
              onClick={() => duplicate(team.id)}
              title="Copy this team along with its agents"
            >
              <Copy {...ICON} />
              Duplicate
            </Button>
          </li>
        ))}
      </ul>
    </Page>
  );
}
