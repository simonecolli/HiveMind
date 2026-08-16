import { api } from '../shared/api/client';
import { useAsync } from '../shared/api/useAsync';
import type { TeamPayload } from '../shared/api/types';
import { Field, Input, Select, Textarea } from '../shared/components/ui';
import { HoverNote } from '../shared/components/HoverNote';
import { OptionalNumberField } from './OptionalNumberField';

/** Team fields, shared between creating and editing. */
export function TeamFields({
  value,
  onChange,
  inheritedProvider,
}: {
  value: TeamPayload;
  onChange: (next: TeamPayload) => void;
  /** The engine the synthesis falls back to: the first agent's. */
  inheritedProvider?: string;
}) {
  // Which engine will actually serve the synthesis, named or inherited.
  const synthesisEngine = value.synthesis_provider ?? inheritedProvider;
  const set = <K extends keyof TeamPayload>(key: K, v: TeamPayload[K]) =>
    onChange({ ...value, [key]: v });

  const { data: engines } = useAsync(() => api.models(), []);
  const choices = (engines ?? []).flatMap((engine) =>
    engine.models.map((model) => ({ provider: engine.provider, model })),
  );
  const chosen = choices.findIndex(
    (c) => c.provider === value.synthesis_provider && c.model === value.synthesis_model,
  );

  return (
    <div className="space-y-5">
      <Field label="Name">
        <Input
          value={value.name}
          onChange={(e) => set('name', e.target.value)}
          placeholder="Board of Directors"
        />
      </Field>

      <Field label="Description">
        <Input
          value={value.description ?? ''}
          onChange={(e) => set('description', e.target.value)}
          placeholder="What this board is for"
        />
      </Field>

      <Field
        label="Protocol"
        hint={
          value.protocol === 'swarm'
            ? 'All agents answer the same context at once, then confront each other next round. No one anchors on whoever spoke first.'
            : 'Each agent reads everyone before it, then speaks. An assembly line.'
        }
      >
        <Select
          value={value.protocol ?? 'relay'}
          onChange={(e) => set('protocol', e.target.value as TeamPayload['protocol'])}
        >
          <option value="relay">Relay - one after another</option>
          <option value="swarm">Swarm - all at once, then confront</option>
        </Select>
      </Field>

      <Field
        label="Default rounds"
        hint="How many times each agent speaks, unless you override it at the start."
      >
        <Select
          value={value.default_max_rounds ?? 2}
          onChange={(e) => set('default_max_rounds', Number(e.target.value))}
        >
          {[1, 2, 3, 4, 5].map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </Select>
      </Field>

      <Field label="Synthesis prompt" hint="Instructs the final node that condenses the debate.">
        <Textarea
          rows={4}
          value={value.synthesis_prompt}
          onChange={(e) => set('synthesis_prompt', e.target.value)}
          placeholder="Condense the debate into an orderly summary..."
        />
      </Field>

      <OptionalNumberField
        label="Synthesis length"
        value={value.synthesis_max_output_length_in_words}
        onChange={(next) => set('synthesis_max_output_length_in_words', next)}
      />

      <Field
        label="Synthesis model"
        hint={
          value.synthesis_model
            ? "The synthesis runs on this instead of the first agent's model."
            : 'Left empty, the synthesis runs on whatever the first agent uses. Name one when the summary has to do work the agents are too small for - counting votes, for instance.'
        }
      >
        <Select
          value={value.synthesis_model ? chosen : ''}
          onChange={(e) => {
            const choice = e.target.value === '' ? null : choices[Number(e.target.value)];
            onChange({
              ...value,
              synthesis_provider: choice?.provider ?? null,
              synthesis_model: choice?.model ?? null,
            });
          }}
        >
          <option value="">Same as the first agent</option>
          {value.synthesis_model && chosen === -1 && (
            <option value={-1}>{value.synthesis_model} (not available now)</option>
          )}
          {(engines ?? []).map((engine) => (
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

      {synthesisEngine === 'lmstudio' ? (
        <HoverNote label="Synthesis context window and thinking are set in LM Studio">
          LM Studio serves the OpenAI API, which has no equivalent of either setting:
          both are chosen on the model as you load it there. Shown here
          they would look adjustable and be ignored.
        </HoverNote>
      ) : (
        <>
          <OptionalNumberField
            label="Synthesis context window"
            hint="Its own, never the first agent's: this node reads the whole transcript, while that agent may be set narrow for a one-line vote."
            min={256}
            step={1024}
            placeholder="Engine default"
            value={value.synthesis_context_window_in_tokens}
            onChange={(next) => set('synthesis_context_window_in_tokens', next)}
          />

          <Field
            label="Synthesis thinking"
            hint="Deliberation before writing the summary. It never reaches the transcript, so a node left to think can spend its budget and write nothing."
          >
            <Select
              value={
                value.synthesis_thinking === null || value.synthesis_thinking === undefined
                  ? ''
                  : String(value.synthesis_thinking)
              }
              onChange={(e) =>
                set('synthesis_thinking', e.target.value === '' ? null : e.target.value === 'true')
              }
            >
              <option value="">Engine default</option>
              <option value="false">Off - write straight away</option>
              <option value="true">On - deliberate first</option>
            </Select>
          </Field>
        </>
      )}
    </div>
  );
}
