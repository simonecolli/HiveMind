import { Field, Input } from '../shared/components/ui';

/**
 * A number that is allowed to be absent, which is the shape several settings
 * share here: an output length, a context window. Empty is never zero - it
 * means the setting is not expressed at all and something below decides.
 */
export function OptionalNumberField({
  label = 'Output length',
  hint = 'Words at most. Leave empty to say nothing about length.',
  value,
  onChange,
  min = 1,
  step = 10,
  placeholder = 'No limit',
}: {
  label?: string;
  hint?: string;
  min?: number;
  step?: number;
  placeholder?: string;
  value: number | null | undefined;
  onChange: (next: number | null) => void;
}) {
  return (
    <Field label={label} hint={hint}>
      <Input
        type="number"
        min={min}
        step={step}
        value={value ?? ''}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
      />
    </Field>
  );
}
