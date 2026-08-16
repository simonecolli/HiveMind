import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react';

const FIELD =
  'w-full rounded-sm border border-line bg-ink px-3 py-2 text-sm text-paper placeholder:text-faint transition-colors focus:border-line-bright focus:outline-none';

export function Button({
  variant = 'primary',
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'ghost' | 'danger' }) {
  const styles = {
    primary: 'bg-signal text-ink hover:bg-signal/90 font-medium',
    ghost: 'border border-line text-muted hover:border-line-bright hover:text-paper',
    danger: 'border border-line text-muted hover:border-alert hover:text-alert',
  }[variant];
  return (
    <button
      {...props}
      className={`inline-flex shrink-0 items-center gap-2 rounded-sm px-3 py-2 text-sm whitespace-nowrap transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${styles} ${className}`}
    />
  );
}

/** Square button for icon-only actions, so the glyph is not stretched. */
export function IconButton({
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center rounded-sm border border-line p-2 text-muted transition-colors hover:border-line-bright hover:text-paper disabled:cursor-not-allowed disabled:opacity-40 ${className}`}
    />
  );
}


export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="edge-mark mb-2 block text-faint">{label}</span>
      {children}
      {hint && <span className="mt-1.5 block text-xs text-faint">{hint}</span>}
    </label>
  );
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={FIELD} />;
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={`${FIELD} resize-y leading-relaxed`} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={FIELD} />;
}

export function Panel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-sm border border-line bg-surface ${className}`}>{children}</div>
  );
}

export function PageHeader({
  overline,
  title,
  actions,
}: {
  overline?: string;
  title: string;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-8 flex items-end justify-between gap-4 border-b border-line pb-5">
      <div>
        {overline && <p className="edge-mark mb-2 text-signal">{overline}</p>}
        <h1 className="text-2xl font-medium tracking-tight text-paper">{title}</h1>
      </div>
      {actions && <div className="flex shrink-0 gap-2">{actions}</div>}
    </header>
  );
}

export function Notice({ tone = 'error', children }: { tone?: 'error' | 'info'; children: ReactNode }) {
  const styles =
    tone === 'error'
      ? 'border-alert/40 bg-alert/10 text-alert'
      : 'border-line bg-surface text-muted';
  return <p className={`rounded-sm border px-3 py-2 text-sm ${styles}`}>{children}</p>;
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-sm border border-dashed border-line px-4 py-10 text-center text-sm text-faint">
      {children}
    </p>
  );
}

/** Agent marker: four quiet tints that cycle with the position. */
export function AgentDot({ position, className = '' }: { position: number; className?: string }) {
  const tints = ['bg-signal', 'bg-violet', 'bg-sky', 'bg-pink'];
  return (
    <span
      aria-hidden
      className={`inline-block size-2 shrink-0 rounded-full ${tints[position % tints.length]} ${className}`}
    />
  );
}
