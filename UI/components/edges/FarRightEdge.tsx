import { BaseEdge, EdgeProps } from '@xyflow/react';

export function FarRightEdge({
  sourceX,
  sourceY,
  targetX,
  targetY,
  style = {},
  markerEnd,
  label,
}: EdgeProps) {
  // Route it to the far right, past the other nodes
  const farRightX = 950;
  const radius = 16;
  
  // Path with rounded corners
  const path = `
    M ${sourceX} ${sourceY} 
    L ${farRightX - radius} ${sourceY} 
    Q ${farRightX} ${sourceY} ${farRightX} ${sourceY - radius} 
    L ${farRightX} ${targetY + radius} 
    Q ${farRightX} ${targetY} ${farRightX - radius} ${targetY} 
    L ${targetX} ${targetY}
  `;

  return (
    <>
      <BaseEdge path={path} markerEnd={markerEnd} style={style} />
      {label && (
        <text
          x={sourceX + 20}
          y={sourceY - 10}
          fill="#ef4444"
          fontSize={12}
          fontWeight="bold"
        >
          {label}
        </text>
      )}
    </>
  );
}
