/**
 * AgentNode — Custom React Flow node for AI agents in the workflow graph.
 *
 * Displays a rounded rectangle with the agent's label and a visual status
 * indicator.  Three status states are supported:
 * - **idle** (purple): Default state before the agent has executed.
 * - **active** (purple with pulse animation): Agent is currently executing.
 * - **completed** (green with checkmark badge): Agent has finished successfully.
 *
 * Has handles on top (target), right (target, for iteration loop edge), and
 * bottom (source) to support the workflow graph's edge routing.
 */
import { Handle, Position } from '@xyflow/react';
import type { NodeStatus } from '@/lib/types';

export function AgentNode({ data }: { data: { label: string; status?: NodeStatus } }) {
  const status: NodeStatus = data.status || 'idle';

  const baseClasses =
    'px-4 py-3 shadow-md rounded-lg min-w-[160px] max-w-[180px] text-center transition-all hover:shadow-lg relative';

  const statusClasses: Record<NodeStatus, string> = {
    idle: 'bg-purple-50 border border-purple-200 hover:border-purple-400',
    active:
      'bg-purple-100 border-2 border-purple-500 shadow-purple-200 shadow-lg animate-pulse',
    completed:
      'bg-green-50 border border-green-300 hover:border-green-400',
  };

  const textClasses: Record<NodeStatus, string> = {
    idle: 'text-purple-900',
    active: 'text-purple-900',
    completed: 'text-green-900',
  };

  const handleColor: Record<NodeStatus, string> = {
    idle: 'bg-purple-500',
    active: 'bg-purple-600',
    completed: 'bg-green-500',
  };

  return (
    <div className={`${baseClasses} ${statusClasses[status]}`}>
      <Handle type="target" position={Position.Top} className={`w-2 h-2 ${handleColor[status]}`} />
      <Handle type="target" position={Position.Right} id="right" className={`w-2 h-2 ${handleColor[status]}`} />
      <div className={`text-sm font-semibold whitespace-pre-line leading-tight ${textClasses[status]}`}>
        {data.label}
      </div>
      {status === 'completed' && (
        <div className="absolute -top-1 -right-1 w-4 h-4 bg-green-500 rounded-full flex items-center justify-center">
          <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </div>
      )}
      <Handle type="source" position={Position.Bottom} className={`w-2 h-2 ${handleColor[status]}`} />
    </div>
  );
}
