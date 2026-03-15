/**
 * FarRightEdge — Custom edge routing for the iteration "No" loop.
 *
 * When validation fails, the workflow loops back from the decision node to
 * the architect supervisor.  This custom edge routes the connection along the
 * far right side of the graph (x=950) to avoid crossing through the grid of
 * domain agent nodes.  The path uses rounded corners (quadratic Bézier curves)
 * for a clean appearance.
 *
 * Styled with a red stroke and "No" label to clearly indicate the failure path.
 */
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
