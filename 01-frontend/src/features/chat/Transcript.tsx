import { useEffect, useRef } from 'react';

import { AgentDot } from '../shared/components/ui';
import type { StreamTurn } from './useDebateStream';

export function Transcript({
  turns,
  selectedId,
  onSelect,
}: {
  turns: StreamTurn[];
  selectedId: number | null;
  onSelect: (turnId: number) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const lastRef = useRef<HTMLElement>(null);

  // Follows the turn being written, without yanking the view if you are
  // reading further up.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const nearBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight < 160;
    if (nearBottom) lastRef.current?.scrollIntoView({ block: 'end' });
  }, [turns]);

  useEffect(() => {
    if (selectedId === null) return;
    document
      .getElementById(`turn-${selectedId}`)
      ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [selectedId]);

  return (
    <div ref={containerRef} className="h-full overflow-y-auto px-8 py-6">
      <ol className="space-y-7">
        {turns.map((turn, index) => (
          <li key={turn.id}>
            <article
              id={`turn-${turn.id}`}
              ref={index === turns.length - 1 ? lastRef : undefined}
              onClick={() => onSelect(turn.id)}
              className={`rise cursor-pointer border-l-2 pl-4 transition-colors ${
                selectedId === turn.id ? 'border-signal' : 'border-line hover:border-line-bright'
              }`}
            >
              <header className="mb-2 flex items-baseline gap-2">
                {turn.kind === 'message' ? (
                  <span aria-hidden className="size-2 shrink-0 rounded-full bg-sky" />
                ) : (
                  <AgentDot position={turn.seq} className="translate-y-[-1px]" />
                )}
                <span className="text-sm text-paper">{turn.agent_name}</span>
                <span className="edge-mark text-faint">
                  {turn.kind === 'synthesis' && 'synthesis'}
                  {turn.kind === 'agent' && `round ${turn.round}`}
                  {turn.kind === 'message' && 'your message'}
                </span>
              </header>

              {turn.title && (
                <p className="edge-mark mb-2 text-signal">{turn.title}</p>
              )}

              <p
                className={`font-read leading-relaxed whitespace-pre-wrap text-paper/90 ${
                  turn.streaming ? 'caret' : ''
                }`}
              >
                {turn.text}
              </p>
            </article>
          </li>
        ))}
      </ol>
    </div>
  );
}
