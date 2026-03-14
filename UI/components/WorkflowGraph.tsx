'use client';

import { useCallback, useEffect, useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { AgentNode } from './nodes/AgentNode';
import { ToolNode } from './nodes/ToolNode';
import { DecisionNode } from './nodes/DecisionNode';
import { StartEndNode } from './nodes/StartEndNode';
import { FarRightEdge } from './edges/FarRightEdge';
import { WORKFLOW_EDGES, buildNodes } from '@/lib/graph.config';

import type { RunStatus } from '@/lib/types';

const nodeTypes = {
  agent: AgentNode,
  tool: ToolNode,
  decision: DecisionNode,
  startEnd: StartEndNode,
};

const edgeTypes = {
  farRight: FarRightEdge,
};

interface WorkflowGraphProps {
  provider: 'AWS' | 'Azure';
  activeNodes?: Set<string>;
  completedNodes?: Set<string>;
  runStatus?: RunStatus;
}

export function WorkflowGraph({ provider, activeNodes, completedNodes, runStatus }: WorkflowGraphProps) {
  const initialNodes = useMemo(
    () => buildNodes(provider, activeNodes, completedNodes, runStatus),
    [provider, activeNodes, completedNodes, runStatus],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(WORKFLOW_EDGES);

  useEffect(() => {
    setNodes(initialNodes);
  }, [initialNodes, setNodes]);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges],
  );

  return (
    <div className="w-full h-full bg-slate-50">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        className="bg-slate-50"
      >
        <Background color="#cbd5e1" gap={16} />
        <Controls className="bg-white shadow-md border border-slate-200 rounded-md" />
        <MiniMap 
          nodeColor={(n) => {
            if (n.type === 'agent') return '#d8b4fe';
            if (n.type === 'tool') return '#f1f5f9';
            if (n.type === 'decision') return '#fde68a';
            return '#bfdbfe';
          }}
          className="bg-white shadow-md border border-slate-200 rounded-md"
        />
      </ReactFlow>
    </div>
  );
}
