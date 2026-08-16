import { Background, ReactFlow, type Edge, type Node } from '@xyflow/react';
import { useMemo } from 'react';
import { useNavigate } from 'react-router';

import type { Agent, DebateProtocol } from '../shared/api/types';
import { Empty } from '../shared/components/ui';
import {
  PreviewAgentNode,
  PreviewIdeaNode,
  PreviewSynthesisNode,
} from './teamPreviewNodes';

const nodeTypes = {
  previewIdea: PreviewIdeaNode,
  previewAgent: PreviewAgentNode,
  previewSynthesis: PreviewSynthesisNode,
};

const COLUMN = 190;
const SWARM_ROW = 70;
const BENCH_ROW = 110;
const IDEA_ID = 'preview-idea';
const SYNTHESIS_ID = 'preview-synthesis';

const LINE = 'var(--color-line-bright)';

/**
 * The running order, drawn.
 *
 * Everything is derived from the agent list, so there is nothing to fetch: the
 * page already knows the topology it is configuring. `rounds` comes from the
 * form rather than from the saved team, so the loop label answers straight away
 * while you are still changing the value.
 */
export function TeamFlowPreview({
  teamId,
  agents,
  rounds,
  protocol,
}: {
  teamId: number;
  agents: Agent[];
  rounds: number;
  protocol: DebateProtocol;
}) {
  const swarm = protocol === 'swarm';
  const navigate = useNavigate();

  const speaking = useMemo(
    () => agents.filter((a) => a.enabled).sort((a, b) => a.position - b.position),
    [agents],
  );
  const benched = useMemo(() => agents.filter((a) => !a.enabled), [agents]);

  const nodes: Node[] = useMemo(() => {
    const built: Node[] = [
      {
        id: IDEA_ID,
        type: 'previewIdea',
        position: { x: 0, y: 0 },
        data: { label: 'Idea' },
        draggable: false,
      },
    ];

    // A relay runs left to right; a swarm stacks the round into one column.
    speaking.forEach((agent, index) => {
      built.push({
        id: String(agent.id),
        type: 'previewAgent',
        position: swarm
          ? { x: COLUMN, y: index * SWARM_ROW }
          : { x: (index + 1) * COLUMN, y: 0 },
        data: { label: agent.name, position: agent.position, enabled: true },
        draggable: false,
      });
    });

    built.push({
      id: SYNTHESIS_ID,
      type: 'previewSynthesis',
      position: {
        x: (swarm ? 2 : speaking.length + 1) * COLUMN,
        y: swarm ? ((speaking.length - 1) * SWARM_ROW) / 2 : 0,
      },
      data: { label: 'Synthesis' },
      draggable: false,
    });

    // The bench sits on its own row, joined to nothing: present, but silent.
    benched.forEach((agent, index) => {
      built.push({
        id: String(agent.id),
        type: 'previewAgent',
        position: {
          x: (swarm ? 1 : index + 1) * COLUMN,
          y: (swarm ? speaking.length * SWARM_ROW : 0) + BENCH_ROW + (swarm ? index * SWARM_ROW : 0),
        },
        data: { label: agent.name, position: agent.position, enabled: false },
        draggable: false,
      });
    });

    return built;
  }, [speaking, benched, swarm]);

  const edges: Edge[] = useMemo(() => {
    if (speaking.length === 0) return [];

    const link = (source: string, target: string): Edge => ({
      id: `pe-${source}-${target}`,
      source,
      target,
      style: { stroke: LINE },
    });

    const ids = speaking.map((a) => String(a.id));
    const built: Edge[] = swarm
      ? // The idea fans out to the whole round, and the round fans back in.
        ids.flatMap((id) => [link(IDEA_ID, id), link(id, SYNTHESIS_ID)])
      : // One line: each agent hands over to the next.
        [IDEA_ID, ...ids, SYNTHESIS_ID]
          .slice(0, -1)
          .map((source, index) => link(source, [...ids, SYNTHESIS_ID][index]));

    // In a swarm the column already is the round, and an arc drawn back over it
    // would cut straight through the nodes. A caption says it better.
    if (rounds > 1 && !swarm) {
      built.push({
        id: 'pe-loop',
        source: String(speaking.at(-1)!.id),
        target: String(speaking[0].id),
        sourceHandle: 'loop-out',
        targetHandle: 'loop-in',
        type: 'smoothstep',
        animated: true,
        label: `${rounds} rounds`,
        labelShowBg: true,
        style: { stroke: 'var(--color-violet)', strokeDasharray: '4 3' },
        labelStyle: { fill: 'var(--color-violet)', fontSize: 10, letterSpacing: '0.14em' },
        labelBgStyle: { fill: 'var(--color-surface)' },
        labelBgPadding: [6, 3] as [number, number],
      });
    }

    return built;
  }, [speaking, rounds, swarm]);

  if (agents.length === 0) {
    return <Empty>Add an agent to see the running order.</Empty>;
  }

  return (
    <div
      className="relative rounded-sm border border-line bg-ink"
      style={{
        height: swarm
          ? 120 + (speaking.length + benched.length) * SWARM_ROW
          : benched.length > 0
            ? 260
            : 180,
      }}
    >
      {swarm && (
        <p className="edge-mark absolute top-3 left-3 z-10 text-violet">
          {rounds > 1 ? `${rounds} rounds, all at once` : 'one round, all at once'}
        </p>
      )}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        colorMode="dark"
        fitView
        fitViewOptions={{ padding: 0.18 }}
        minZoom={0.2}
        maxZoom={1}
        proOptions={{ hideAttribution: true }}
        onNodeClick={(_, node) => {
          if (node.type === 'previewAgent') navigate(`/teams/${teamId}/agents/${node.id}`);
        }}
        // An illustration, not a canvas to handle: no dragging, no zooming, and
        // the wheel keeps scrolling the page underneath.
        nodesDraggable={false}
        nodesConnectable={false}
        panOnDrag={false}
        zoomOnScroll={false}
        zoomOnPinch={false}
        zoomOnDoubleClick={false}
        preventScrolling={false}
      >
        <Background color="var(--color-line)" gap={22} size={1} />
      </ReactFlow>
    </div>
  );
}
