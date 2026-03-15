/**
 * DecisionNode — Diamond-shaped decision node for validation routing.
 *
 * Represents the "Validation Success?" decision point in the workflow graph.
 * Rendered as a rotated square (diamond shape) with:
 * - Top handle (target): Receives edge from the validation reducer.
 * - Bottom handle ("yes"): Green, routes to the end node when validation passes.
 * - Right handle ("no"): Red, routes back to architect supervisor for re-iteration.
 */
import { Handle, Position } from '@xyflow/react';

export function DecisionNode({ data }: { data: any }) {
  return (
    <div className="w-24 h-24 relative flex items-center justify-center group">
      <div className="absolute inset-0 bg-amber-50 border-2 border-amber-300 transform rotate-45 rounded-sm transition-all group-hover:border-amber-500 shadow-sm"></div>
      <div className="relative z-10 text-[10px] font-bold text-amber-900 text-center px-2 leading-tight">{data.label}</div>
      <Handle type="target" position={Position.Top} className="w-2 h-2 bg-amber-500" />
      <Handle type="source" position={Position.Bottom} id="yes" className="w-2 h-2 bg-green-500" />
      <Handle type="source" position={Position.Right} id="no" className="w-2 h-2 bg-red-500" />
    </div>
  );
}
