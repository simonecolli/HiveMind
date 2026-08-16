import { useEffect, useRef, useState } from 'react';

import type { Canvas, TurnKind } from '../shared/api/types';

export interface StreamTurn {
  id: number;
  agent_id: number;
  agent_name: string;
  pass_no: number;
  round: number;
  seq: number;
  kind: TurnKind;
  title: string | null;
  text: string;
  streaming: boolean;
}

interface TurnStartEvent {
  turn_id: number;
  agent_id: number;
  agent_name: string;
  pass_no: number;
  round: number;
  seq: number;
  kind: TurnKind;
}

export interface DebateStream {
  active: boolean;
  turns: StreamTurn[];
  canvas: Canvas | null;
  status: 'connecting' | 'running' | 'done' | 'error' | 'stopped';
  error: string | null;
}

const IDLE: DebateStream = {
  active: false,
  turns: [],
  canvas: null,
  status: 'connecting',
  error: null,
};

/**
 * Follows a running debate over SSE.
 *
 * The server closes the stream when the debate ends, but `EventSource`
 * reconnects on its own: without an explicit close on `session.end` the buffer
 * would replay forever.
 */
export function useDebateStream(sessionId: string | undefined): DebateStream {
  const [state, setState] = useState<DebateStream>(IDLE);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!sessionId) {
      setState(IDLE);
      return;
    }

    setState({ ...IDLE, active: true });
    const source = new EventSource(`/api/v1/sessions/${sessionId}/stream`);
    sourceRef.current = source;

    const on = <T,>(name: string, handler: (data: T) => void) =>
      source.addEventListener(name, (event) =>
        handler(JSON.parse((event as MessageEvent).data) as T),
      );

    on('session.start', () => setState((s) => ({ ...s, status: 'running' })));

    // The backend identifies a turn by `turn_id`; local state calls it `id`.
    on<TurnStartEvent>('turn.start', (data) =>
      setState((s) => ({
        ...s,
        turns: [
          ...s.turns.filter((t) => t.id !== data.turn_id),
          {
            id: data.turn_id,
            agent_id: data.agent_id,
            agent_name: data.agent_name,
            pass_no: data.pass_no,
            round: data.round,
            seq: data.seq,
            kind: data.kind,
            title: null,
            text: '',
            streaming: true,
          },
        ],
      })),
    );

    on('turn.delta', (data: { turn_id: number; text: string }) =>
      setState((s) => ({
        ...s,
        turns: s.turns.map((t) =>
          t.id === data.turn_id ? { ...t, text: t.text + data.text } : t,
        ),
      })),
    );

    on('turn.end', (data: { turn_id: number; title: string | null }) =>
      setState((s) => ({
        ...s,
        turns: s.turns.map((t) =>
          t.id === data.turn_id ? { ...t, title: data.title, streaming: false } : t,
        ),
      })),
    );

    on('graph', (canvas: Canvas) => setState((s) => ({ ...s, canvas })));

    on('error', (data: { message: string }) =>
      setState((s) => ({ ...s, error: data.message })),
    );

    on('session.end', (data: { status: 'done' | 'error' | 'stopped' }) => {
      setState((s) => ({ ...s, status: data.status }));
      source.close();
    });

    // Transport error: the debate is no longer in memory (backend restarted) or
    // the connection dropped.
    source.onerror = () => {
      setState((s) =>
        s.status === 'connecting'
          ? { ...s, status: 'error', error: 'No debate is running for this session.' }
          : s,
      );
      source.close();
    };

    return () => source.close();
  }, [sessionId]);

  return state;
}
