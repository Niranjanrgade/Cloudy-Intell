/**
 * useRunOrchestration — Central orchestration hook for the CloudyIntel UI.
 *
 * This hook manages the entire lifecycle of a cloud architecture generation run:
 *
 * 1. **Thread creation**: Creates a new LangGraph thread via the `/api/threads` endpoint.
 * 2. **LangGraph Studio**: Opens a LangGraph Studio tab for real-time run observation.
 * 3. **SSE streaming**: Initiates a streaming run via `/api/runs/stream` and processes
 *    Server-Sent Events (SSE) to update the UI in real time.
 * 4. **Node status tracking**: Maps backend node names (e.g. "architect_phase:compute_architect")
 *    to UI node IDs and manages active/completed sets for the workflow graph visualization.
 * 5. **Chat messages**: Maintains the chat history shown in the CopilotSidebar, including
 *    user messages, status updates (which node is currently executing), and assistant responses.
 * 6. **Final state fetch**: After the stream ends, fetches the complete final state from
 *    `/api/threads/{threadId}/state` to populate the CompareView with architecture results.
 *
 * The hook exposes `runStatus` (idle/running/completed/error), node status sets, messages,
 * the architecture result, and the `startRun` callback for the UI to consume.
 */

'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import type { RunStatus, ChatMessage, ArchitectureState } from '@/lib/types';
import { BACKEND_TO_UI_NODE, NODE_LABELS } from '@/lib/node-mapping';

const WELCOME_MESSAGE: ChatMessage = {
  id: 1,
  role: 'assistant',
  content:
    'Hello! I am CloudyIntel, your agentic AI assistant for Cloud Solution Architects. I use LangGraph to automate and validate complex cloud architectures. What would you like to build today?',
};

export function useRunOrchestration() {
  const [runStatus, setRunStatus] = useState<RunStatus>('idle');
  const [activeNodes, setActiveNodes] = useState<Set<string>>(new Set());
  const [completedNodes, setCompletedNodes] = useState<Set<string>>(new Set());
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE]);
  const [architectureResult, setArchitectureResult] =
    useState<ArchitectureState | null>(null);
  const [studioUrl, setStudioUrl] = useState<string | null>(null);
  const threadIdRef = useRef<string | null>(null);
  const msgIdRef = useRef(100);
  const timeoutIdsRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  // Clean up pending timeouts on unmount
  useEffect(() => {
    return () => {
      timeoutIdsRef.current.forEach(clearTimeout);
    };
  }, []);

  const startRun = useCallback(async (userProblem: string) => {
    const userMsg: ChatMessage = {
      id: Date.now(),
      role: 'user',
      content: userProblem,
    };
    setMessages((prev) => [...prev, userMsg]);
    setRunStatus('running');
    setActiveNodes(new Set());
    setCompletedNodes(new Set());
    timeoutIdsRef.current.forEach(clearTimeout);
    timeoutIdsRef.current = [];

    try {
      // 1. Create a thread
      const threadRes = await fetch('/api/threads', { method: 'POST' });
      if (!threadRes.ok) throw new Error('Failed to create thread');
      const { thread_id } = await threadRes.json();
      threadIdRef.current = thread_id;

      // Open LangGraph Studio in a new tab
      const baseUrl =
        process.env.NEXT_PUBLIC_LANGGRAPH_API_URL || 'http://localhost:2024';
      const url = `https://smith.langchain.com/studio/thread/${thread_id}?baseUrl=${encodeURIComponent(baseUrl)}`;
      setStudioUrl(url);
      window.open(url, '_blank', 'noopener');
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 0.1,
          role: 'assistant',
          content: 'Opened LangGraph Studio — track the run in real time.',
          link: url,
        },
      ]);

      // 2. Start streaming run
      const streamRes = await fetch('/api/runs/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ thread_id, user_problem: userProblem }),
      });
      if (!streamRes.ok || !streamRes.body)
        throw new Error('Failed to start streaming run');

      const reader = streamRes.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let lastArchState: ArchitectureState | null = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.replace(/^data: /, '').trim();
          if (!trimmed || trimmed === '[DONE]') continue;

          let parsed: { event: string; data: unknown };
          try {
            parsed = JSON.parse(trimmed);
          } catch {
            continue;
          }

          if (parsed.event === 'error') {
            const errData = parsed.data as { message?: string };
            throw new Error(errData.message || 'Stream error');
          }

          if (
            parsed.event === 'updates' &&
            parsed.data &&
            typeof parsed.data === 'object'
          ) {
            const updates = parsed.data as Record<
              string,
              Partial<ArchitectureState>
            >;
            for (const nodeName of Object.keys(updates)) {
              const uiNodeId = BACKEND_TO_UI_NODE[nodeName];
              const label = NODE_LABELS[nodeName] || nodeName;

              if (uiNodeId) {
                setActiveNodes((prev) => {
                  const next = new Set(prev);
                  next.add(uiNodeId);
                  return next;
                });

                const tid = setTimeout(() => {
                  setActiveNodes((prev) => {
                    const next = new Set(prev);
                    next.delete(uiNodeId);
                    return next;
                  });
                  setCompletedNodes((prev) => {
                    const next = new Set(prev);
                    next.add(uiNodeId);
                    return next;
                  });
                }, 600);
                timeoutIdsRef.current.push(tid);
              }

              setMessages((prev) => [
                ...prev,
                {
                  id: ++msgIdRef.current,
                  role: 'status',
                  content: label,
                },
              ]);

              const nodeState = updates[nodeName];
              lastArchState = { ...(lastArchState ?? {}), ...nodeState };
            }
          }
        }
      }

      // 3. Fetch final state
      if (threadIdRef.current) {
        const stateRes = await fetch(
          `/api/threads/${threadIdRef.current}/state`,
        );
        if (stateRes.ok) {
          const fullState = await stateRes.json();
          const values = (fullState.values || fullState) as ArchitectureState;
          setArchitectureResult(values);
          lastArchState = values;
        }
      }

      // 4. Show final summary message
      const summary =
        lastArchState?.architecture_summary ||
        'Architecture generation completed. Switch to the Compare view to see the results.';
      setMessages((prev) => [
        ...prev,
        { id: Date.now(), role: 'assistant', content: summary },
      ]);
      setRunStatus('completed');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'An error occurred';
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          role: 'assistant',
          content: `Error: ${msg}. Please try again.`,
        },
      ]);
      setRunStatus('error');
    }
  }, []);

  return {
    runStatus,
    activeNodes,
    completedNodes,
    messages,
    setMessages,
    architectureResult,
    studioUrl,
    startRun,
  };
}
