import type { ReactNode } from 'react';
import { TriangleAlert } from 'lucide-react';

import { ICON } from '../icons';

/**
 * A setting that does not apply here, and why.
 *
 * Hiding a control with no explanation reads as a missing feature; leaving it
 * visible but inert is worse, since it invites you to set something that will
 * be ignored. This says the field is gone on purpose and where the equivalent
 * lives, without spending a whole row of the form on it.
 */
export function HoverNote({ label, children }: { label: string; children: ReactNode }) {
  return (
    <span
      // Focusable so the explanation is reachable without a pointer.
      tabIndex={0}
      className="group relative inline-flex items-center gap-1.5 text-xs text-faint"
    >
      <TriangleAlert {...ICON} className="text-alert" />
      {label}
      <span
        role="tooltip"
        className="pointer-events-none absolute left-0 top-full z-10 mt-2 w-72 rounded border border-line bg-surface p-3 leading-relaxed text-muted opacity-0 shadow-lg transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
      >
        {children}
      </span>
    </span>
  );
}
