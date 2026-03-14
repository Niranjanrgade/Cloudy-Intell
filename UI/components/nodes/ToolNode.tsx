import { Handle, Position } from '@xyflow/react';

export function ToolNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-2 shadow-sm rounded-full bg-white border-2 border-dashed border-gray-300 min-w-[140px] text-center transition-all hover:border-gray-500">
      <Handle type="target" position={Position.Top} className="w-2 h-2 bg-gray-400" />
      <div className="text-xs font-medium text-gray-600 whitespace-pre-line">{data.label}</div>
      <Handle type="source" position={Position.Bottom} className="w-2 h-2 bg-gray-400" />
    </div>
  );
}
