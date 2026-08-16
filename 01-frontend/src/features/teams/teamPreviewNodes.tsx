import { Handle, Position, type NodeProps } from '@xyflow/react';

import { AgentDot } from '../shared/components/ui';

/**
 * Compact nodes for the running-order preview: the same visual language as the
 * debate canvas, minus the body text. Here only the order matters.
 */

interface Data {
  label: string;
  position?: number;
  enabled?: boolean;
}

function Frame({
  children,
  dashed = false,
}: {
  children: React.ReactNode;
  dashed?: boolean;
}) {
  return (
    <div
      className={`sprockets w-40 rounded-sm border bg-surface py-2 pr-3 pl-3 transition-colors ${
        dashed ? 'border-dashed border-line' : 'border-line hover:border-line-bright'
      }`}
    >
      {children}
    </div>
  );
}

export function PreviewIdeaNode() {
  return (
    <Frame>
      <p className="edge-mark text-signal">Idea</p>
      <Handle type="source" position={Position.Right} className="!bg-line-bright" />
    </Frame>
  );
}

export function PreviewAgentNode({ data }: NodeProps) {
  const d = data as unknown as Data;
  return (
    <Frame dashed={!d.enabled}>
      <div className="flex items-center gap-2">
        <AgentDot position={d.position ?? 0} className={d.enabled ? '' : 'opacity-40'} />
        <span className={`truncate text-xs ${d.enabled ? 'text-paper' : 'text-faint'}`}>
          {d.label}
        </span>
      </div>
      {/* `ml-4` lines it up under the name, past the dot and its gap. */}
      {!d.enabled && <p className="edge-mark mt-1 ml-4 text-faint">off</p>}
      <Handle type="target" position={Position.Left} className="!bg-line-bright" />
      <Handle type="source" position={Position.Right} className="!bg-line-bright" />
      {/* The loop back to the first speaker gets its own handles on top, so it
          arches over the row instead of threading behind the nodes. */}
      <Handle
        id="loop-in"
        type="target"
        position={Position.Top}
        style={{ left: '35%' }}
        className="!bg-violet/60"
      />
      <Handle
        id="loop-out"
        type="source"
        position={Position.Top}
        style={{ left: '65%' }}
        className="!bg-violet/60"
      />
    </Frame>
  );
}

export function PreviewSynthesisNode() {
  return (
    <Frame>
      <p className="edge-mark text-violet">Synthesis</p>
      <Handle type="target" position={Position.Left} className="!bg-line-bright" />
    </Frame>
  );
}
