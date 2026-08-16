import {
  Background,
  Controls,
  ReactFlow,
  useReactFlow,
  useStore,
  type Node,
} from '@xyflow/react';
import { useEffect, useMemo, useRef } from 'react';

import type { Canvas } from '../shared/api/types';
import type { StreamTurn } from '../chat/useDebateStream';
import { AgentNode, IdeaNode, MessageNode, SynthesisNode } from './nodes';

const nodeTypes = {
  idea: IdeaNode,
  agent: AgentNode,
  synthesis: SynthesisNode,
  message: MessageNode,
};

const NODE_WIDTH = 224;
const NODE_HEIGHT = 86;
/** How close to the right edge a new node may sit before the view follows it. */
const EDGE_MARGIN = 24;

/**
 * Keeps the newest node in view without moving the ground under the reader.
 *
 * It frames once, when the canvas first has something in it. After that the
 * zoom is never touched again: re-fitting on every arriving node rescaled the
 * whole strip several times a minute, which reads as the canvas resetting.
 *
 * Panning then moves by the smallest amount that brings the new node fully
 * inside - never by centring on it. Centring was the reason earlier nodes
 * appeared to be deleted when the round changed: a new round starts a new
 * column 320px to the right and back at the top row, and putting that node in
 * the middle of the pane pushes the column the reader was reading off the left
 * edge. Nothing was ever removed from the graph; it had simply left the frame.
 * The fit-view button still gives the whole picture on demand.
 */
function KeepInView({ nodes }: { nodes: Node[] }) {
  const { setViewport } = useReactFlow();
  const paneWidth = useStore((state) => state.width);
  const paneHeight = useStore((state) => state.height);
  const zoomRef = useRef(1);
  const framed = useRef(false);

  useEffect(() => {
    if (nodes.length === 0 || !paneWidth || !paneHeight) return;

    const left = Math.min(...nodes.map((n) => n.position.x));
    const right = Math.max(...nodes.map((n) => n.position.x + NODE_WIDTH));
    const top = Math.min(...nodes.map((n) => n.position.y));
    const bottom = Math.max(...nodes.map((n) => n.position.y + NODE_HEIGHT));
    const width = right - left + EDGE_MARGIN * 2;
    const height = bottom - top + EDGE_MARGIN * 2;

    // The zoom only ever decreases. A debate only grows, so the frame that
    // holds it can only widen; letting it zoom back in on a later node is what
    // made the strip lurch, and re-fitting freely rescaled it several times a
    // minute. Monotonic means the picture is stable: it settles outwards.
    const zoom = Math.min(zoomRef.current, paneWidth / width, paneHeight / height, 1);
    zoomRef.current = zoom;

    void setViewport(
      {
        x: paneWidth / 2 - ((left + right) / 2) * zoom,
        y: paneHeight / 2 - ((top + bottom) / 2) * zoom,
        zoom,
      },
      // The first frame lands instantly; later ones ease, so a new column
      // arriving reads as the view opening up rather than as a jump.
      { duration: framed.current ? 400 : 0 },
    );
    framed.current = true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes.length, paneWidth, paneHeight]);

  return null;
}

export function DebateCanvas({
  canvas,
  turns,
  selectedId,
  onSelect,
}: {
  canvas: Canvas | null;
  turns: StreamTurn[];
  selectedId: number | null;
  onSelect: (turnId: number) => void;
}) {
  // A node shows a title and a colour index - never the streaming text. The
  // turns prop changes identity on every token, so keying on the whole of it
  // rebuilt every node object several times a second: React Flow then had to
  // re-measure nodes it had already laid out, which reads as the canvas
  // reloading while the agents write. This signature only moves when a turn
  // starts or is titled.
  const marks = turns.map((t) => `${t.id}:${t.seq}:${t.title ?? ''}`).join('|');
  const byId = useMemo(
    () => new Map(turns.map((t) => [String(t.id), { title: t.title, seq: t.seq }])),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [marks],
  );

  const nodes: Node[] = useMemo(
    () =>
      (canvas?.nodes ?? []).map((node) => {
        const turn = byId.get(node.id);
        return {
          id: node.id,
          type: node.type,
          position: node.position,
          data: {
            ...node.data,
            title: turn?.title ?? null,
            tint: turn?.seq ?? 0,
            selected: selectedId !== null && node.id === String(selectedId),
          },
        };
      }),
    [canvas, byId, selectedId],
  );

  const edges = useMemo(
    () =>
      (canvas?.edges ?? []).map((edge) => ({
        ...edge,
        style: { stroke: 'var(--color-line-bright)' },
      })),
    [canvas],
  );

  if (!canvas || canvas.nodes.length === 0) {
    return (
      <div className="flex h-full items-center justify-center px-8 text-center">
        <p className="text-sm text-faint">
          The canvas builds itself as the agents speak.
        </p>
      </div>
    );
  }

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      colorMode="dark"
      // No `fitView` prop: React Flow runs its own fit once the nodes are
      // measured, which would race with (and overwrite) the framing below.
      // `KeepInView` is the single place that decides what is on screen.
      //
      // `minZoom` is lowered from the 0.5 default so a long strip can still be
      // fitted with the controls' fit-view button.
      minZoom={0.15}
      proOptions={{ hideAttribution: true }}
      onNodeClick={(_, node) => {
        if (node.id !== 'idea') onSelect(Number(node.id));
      }}
      nodesDraggable={false}
      nodesConnectable={false}
    >
      <KeepInView nodes={nodes} />
      <Background color="var(--color-line)" gap={28} size={1} />
      <Controls showInteractive={false} className="!border-line !bg-surface" />
    </ReactFlow>
  );
}
