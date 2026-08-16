import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router';
import { Check, Trash2 } from 'lucide-react';

import { ApiError, api } from '../shared/api/client';
import type { AgentPayload } from '../shared/api/types';
import { useAsync } from '../shared/api/useAsync';
import { Page } from '../shared/components/Layout';

import { ICON } from '../shared/icons';
import {
  Button,
  Field,
  Input,
  Notice,
  PageHeader,
  Select,
  Textarea,
} from '../shared/components/ui';
import { HoverNote } from '../shared/components/HoverNote';
import { OptionalNumberField } from './OptionalNumberField';

const EMPTY: AgentPayload = {
  name: '',
  system_prompt: '',
  provider: 'ollama',
  model: '',
  max_output_length_in_words: null,
  context_window_in_tokens: null,
  thinking: null,
  enabled: true,
};

/**
 * One page for both creating and editing: whether `agentId` is present in the
 * route decides between POST and PATCH.
 */
export function AgentEditorPage() {
  const { teamId, agentId } = useParams();
  const navigate = useNavigate();
  const id = Number(teamId);
  const editing = agentId !== undefined;

  const { data: team, loading } = useAsync(() => api.team(id), [id]);
  const { data: models } = useAsync(() => api.models(), []);

  const [value, setValue] = useState<AgentPayload>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!team) return;
    const existing = editing ? team.agents.find((a) => a.id === Number(agentId)) : undefined;
    if (existing) {
      setValue({
        name: existing.name,
        system_prompt: existing.system_prompt,
        provider: existing.provider,
        model: existing.model,
        max_output_length_in_words: existing.max_output_length_in_words,
        context_window_in_tokens: existing.context_window_in_tokens,
        thinking: existing.thinking,
        enabled: existing.enabled,
      });
    } else if (!editing) {
      // A new agent inherits the engine and model of the one before it.
      const previous = team.agents.at(-1);
      setValue((v) => ({
        ...v,
        provider: v.model ? v.provider : (previous?.provider ?? 'ollama'),
        model: v.model || previous?.model || '',
      }));
    }
  }, [team, agentId, editing]);

  const set = <K extends keyof AgentPayload>(key: K, v: AgentPayload[K]) =>
    setValue({ ...value, [key]: v });

  const incomplete = !value.name.trim() || !value.system_prompt.trim() || !value.model;

  async function save() {
    setSaving(true);
    setError(null);
    try {
      if (editing) await api.updateAgent(Number(agentId), value);
      else await api.addAgent(id, value);
      navigate(`/teams/${id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
      setSaving(false);
    }
  }

  async function remove() {
    await api.deleteAgent(Number(agentId));
    navigate(`/teams/${id}`);
  }

  if (loading) return <Page><p className="text-sm text-faint">Loading...</p></Page>;

  // A flat list behind the grouped select: the option value is an index, so one
  // click sets engine and model together. Encoding both in a string would break
  // on Ollama names, which already contain a colon.
  const choices = (models ?? []).flatMap((engine) =>
    engine.models.map((model) => ({ provider: engine.provider, label: engine.label, model })),
  );
  const selected = choices.findIndex(
    (c) => c.provider === value.provider && c.model === value.model,
  );
  const missing = value.model && selected === -1;

  return (
    <Page>
      <PageHeader
        overline={`Teams / ${team?.name ?? ''}`}
        title={editing ? 'Edit agent' : 'New agent'}
        actions={
          <>
            <Button variant="ghost" onClick={() => navigate(`/teams/${id}`)}>
              Cancel
            </Button>
            {editing && (
              <Button variant="danger" onClick={remove}>
                <Trash2 {...ICON} />
                Delete
              </Button>
            )}
            <Button onClick={save} disabled={incomplete || saving}>
              <Check {...ICON} />
              {saving ? 'Saving...' : 'Save agent'}
            </Button>
          </>
        }
      />

      {error && (
        <div className="mb-5">
          <Notice>{error}</Notice>
        </div>
      )}

      <div className="space-y-5">
        <Field label="Name">
          <Input
            value={value.name}
            onChange={(e) => set('name', e.target.value)}
            placeholder="Devil's Advocate"
          />
        </Field>

        <Field
          label="Model"
          hint={
            missing
              ? // The engine's own label, not its internal name: everywhere else
                // this UI says "LM Studio", not "lmstudio".
                `${(models ?? []).find((e) => e.provider === value.provider)?.label ?? value.provider} does not currently offer ${value.model}. Start that engine, or pick another model.`
              : choices.length
                ? 'Grouped by the engine that serves it.'
                : 'No engine is responding. Start Ollama or LM Studio to fill this list.'
          }
        >
          <Select
            value={selected}
            onChange={(e) => {
              const choice = choices[Number(e.target.value)];
              if (choice) setValue({ ...value, provider: choice.provider, model: choice.model });
            }}
          >
            <option value={-1}>
              {missing ? `${value.model} (not available now)` : 'Pick a model...'}
            </option>
            {(models ?? []).map((engine) => (
              <optgroup key={engine.provider} label={engine.label}>
                {engine.models.map((model) => (
                  <option
                    key={`${engine.provider}:${model}`}
                    value={choices.findIndex(
                      (c) => c.provider === engine.provider && c.model === model,
                    )}
                  >
                    {model}
                  </option>
                ))}
              </optgroup>
            ))}
          </Select>
        </Field>

        <Field
          label="System prompt"
          hint="The agent's character. Length goes in the field below, not in here."
        >
          <Textarea
            rows={10}
            value={value.system_prompt}
            onChange={(e) => set('system_prompt', e.target.value)}
            placeholder="You are the devil's advocate. Find the weak points without mercy..."
          />
        </Field>

        <OptionalNumberField
          value={value.max_output_length_in_words}
          onChange={(next) => set('max_output_length_in_words', next)}
        />

        {value.provider === 'lmstudio' ? (
          <HoverNote label="Context window and thinking are set in LM Studio">
            LM Studio serves the OpenAI API, which has no equivalent of either setting:
            both are chosen on the model as you load it there. Shown here they would look
            adjustable and be ignored.
          </HoverNote>
        ) : (
          <>
            <OptionalNumberField
              label="Context window"
              hint="Tokens of debate this agent is given to read. Empty uses the engine's own, which is generous - so this mostly saves memory rather than buying room: the same model held 4.2 GB at 32k and 3.4 GB at 8k, which decides whether a swarm keeps two models resident."
              min={256}
              step={1024}
              placeholder="Engine default"
              value={value.context_window_in_tokens}
              onChange={(next) => set('context_window_in_tokens', next)}
            />

            <Field
              label="Thinking"
              hint="Deliberation before answering. It never reaches the transcript, so a model left to think can spend its whole budget and answer nothing - and where it does answer, the reasoning can break tags a team counts on."
            >
              <Select
                value={
                  value.thinking === null || value.thinking === undefined
                    ? ''
                    : String(value.thinking)
                }
                onChange={(e) =>
                  set('thinking', e.target.value === '' ? null : e.target.value === 'true')
                }
              >
                <option value="">Engine default</option>
                <option value="false">Off - answer straight away</option>
                <option value="true">On - deliberate first</option>
              </Select>
            </Field>
          </>
        )}

        <label className="flex items-center gap-2.5 text-sm text-muted">
          <input
            type="checkbox"
            checked={value.enabled ?? true}
            onChange={(e) => set('enabled', e.target.checked)}
            className="accent-signal"
          />
          Takes part in debates
        </label>
      </div>
    </Page>
  );
}
