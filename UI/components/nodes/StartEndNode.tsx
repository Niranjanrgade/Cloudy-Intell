/**
 * StartEndNode — Rounded pill node for workflow start and end points.
 *
 * Used for two nodes:
 * - **Start** (blue): "User Query (AWS/Azure)" — entry point of the workflow.
 *   Only has a source handle (bottom) since nothing connects into it.
 * - **End** (emerald green): "Architect Solution Response" — final output.
 *   Only has a target handle (top) since nothing connects out of it.
 *
 * The `data.type` field ("start" or "end") controls the color scheme and
 * which handles are rendered.
 */
import { Handle, Position } from '@xyflow/react';

export function StartEndNode({ data }: { data: any }) {
  const isStart = data.type === 'start';
  return (
    <div className={`px-6 py-2 shadow-sm rounded-full border-2 min-w-[120px] text-center transition-all ${isStart ? 'bg-blue-50 border-blue-200 hover:border-blue-400' : 'bg-emerald-50 border-emerald-200 hover:border-emerald-400'}`}>
      {!isStart && <Handle type="target" position={Position.Top} className={`w-2 h-2 ${isStart ? 'bg-blue-500' : 'bg-emerald-500'}`} />}
      <div className={`text-sm font-bold whitespace-pre-line ${isStart ? 'text-blue-900' : 'text-emerald-900'}`}>{data.label}</div>
      {isStart && <Handle type="source" position={Position.Bottom} className={`w-2 h-2 ${isStart ? 'bg-blue-500' : 'bg-emerald-500'}`} />}
    </div>
  );
}
