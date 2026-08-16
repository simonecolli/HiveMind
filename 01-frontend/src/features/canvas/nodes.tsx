import { Handle, Position, type NodeProps } from '@xyflow/react';

/**
 * Nodes are treated as frames on a contact sheet: sprocket holes along the
 * edge, a mono marking on top, the title set in serif inside.
 */

const TINTS = ['bg-signal', 'bg-violet', 'bg-sky', 'bg-pink'];

interface Data {
  label: string;
  agent_name?: string;
  round?: number;
  tint?: number;
  selected?: boolean;
  title?: string | null;
}

function Frame({
  children,
  active,
  className = '',
}: {
  children: React.ReactNode;
  active?: boolean;
  className?: string;
}) {
  return (
    <div
      className={`sprockets w-56 rounded-sm border bg-surface pl-3 transition-colors ${
        active ? 'border-signal' : 'border-line hover:border-line-bright'
      } ${className}`}
    >
      {children}
    </div>
  );
}

export function IdeaNode({ data }: NodeProps) {
  const d = data as unknown as Data;
  return (
    <Frame className="py-3 pr-3">
      <p className="edge-mark mb-1.5 text-signal">Idea</p>
      <p className="font-read text-sm leading-snug text-paper">{d.label}</p>
      <Handle type="source" position={Position.Right} className="!bg-line-bright" />
    </Frame>
  );
}

export function AgentNode({ data }: NodeProps) {
  const d = data as unknown as Data;
  return (
    <Frame active={d.selected} className="py-3 pr-3">
      <div className="mb-1.5 flex items-center gap-2">
        <span
          aria-hidden
          className={`size-1.5 rounded-full ${TINTS[(d.tint ?? 0) % TINTS.length]}`}
        />
        <span className="edge-mark truncate text-muted">
          {d.agent_name} - R{d.round}
        </span>
      </div>
      <p className="font-read text-sm leading-snug text-paper">
        {d.title || <span className="text-faint">Writing...</span>}
      </p>
      <Handle type="target" position={Position.Left} className="!bg-line-bright" />
      <Handle type="source" position={Position.Right} className="!bg-line-bright" />
    </Frame>
  );
}

export function MessageNode({ data }: NodeProps) {
  const d = data as unknown as Data;
  return (
    <Frame active={d.selected} className="py-3 pr-3">
      <p className="edge-mark mb-1.5 text-sky">You</p>
      <p className="font-read text-sm leading-snug text-paper">{d.label}</p>
      <Handle type="target" position={Position.Left} className="!bg-line-bright" />
      <Handle type="source" position={Position.Right} className="!bg-line-bright" />
    </Frame>
  );
}

export function SynthesisNode({ data }: NodeProps) {
  const d = data as unknown as Data;
  return (
    <Frame active={d.selected} className="border-dashed py-3 pr-3">
      <p className="edge-mark mb-1.5 text-violet">Synthesis</p>
      <p className="font-read text-sm leading-snug text-paper">
        {d.title || <span className="text-faint">Writing...</span>}
      </p>
      <Handle type="target" position={Position.Left} className="!bg-line-bright" />
      {/* A synthesis is only the end until a follow-up carries on from it. */}
      <Handle type="source" position={Position.Right} className="!bg-line-bright" />
    </Frame>
  );
}

