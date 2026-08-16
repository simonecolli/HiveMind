import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Check } from 'lucide-react';

import { ApiError, api } from '../shared/api/client';
import type { TeamPayload } from '../shared/api/types';
import { Page } from '../shared/components/Layout';

import { ICON } from '../shared/icons';
import { Button, Notice, PageHeader } from '../shared/components/ui';
import { TeamFields } from './TeamFields';

const EMPTY: TeamPayload = {
  name: '',
  description: '',
  protocol: 'relay',
  default_max_rounds: 2,
  synthesis_max_output_length_in_words: null,
  synthesis_provider: null,
  synthesis_model: null,
  synthesis_context_window_in_tokens: null,
  synthesis_thinking: null,
  synthesis_prompt:
    'Condense the debate into an orderly summary: the direction that emerged, the objections still open, and the concrete next steps.',
};

export function TeamCreatePage() {
  const navigate = useNavigate();
  const [value, setValue] = useState<TeamPayload>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const incomplete = !value.name.trim() || !value.synthesis_prompt.trim();

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const team = await api.createTeam(value);
      navigate(`/teams/${team.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
      setSaving(false);
    }
  }

  return (
    <Page>
      <PageHeader
        overline="Teams / new"
        title="New team"
        actions={
          <>
            <Button variant="ghost" onClick={() => navigate('/teams')}>
              Cancel
            </Button>
            <Button onClick={save} disabled={incomplete || saving}>
              <Check {...ICON} />
              {saving ? 'Saving...' : 'Create team'}
            </Button>
          </>
        }
      />

      {error && (
        <div className="mb-5">
          <Notice>{error}</Notice>
        </div>
      )}

      <TeamFields value={value} onChange={setValue} />

      <p className="mt-6 text-xs text-faint">You add agents next, on the team page.</p>
    </Page>
  );
}
