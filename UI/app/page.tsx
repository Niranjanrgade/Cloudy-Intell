/**
 * Home Page — Main layout for the CloudyIntel application.
 *
 * This is the root page component that assembles the three-panel layout:
 *
 * 1. **SidebarNavigator** (left): Navigation between AWS, Azure, and Compare views.
 * 2. **Main content area** (center): Either a WorkflowGraph (for AWS/Azure views)
 *    or a CompareView (for comparison mode).
 * 3. **CopilotSidebar** (right or bottom): Chat interface for submitting
 *    architecture problems and viewing real-time agent status updates.
 *
 * The `useRunOrchestration` hook manages all run state (status, active/completed
 * nodes, messages, architecture results) and is shared across all child components.
 *
 * In Compare mode, the layout switches from a horizontal split (graph + sidebar)
 * to a vertical split (comparison + bottom chat) for better use of screen space.
 */
'use client';

import { useState } from 'react';
import { CopilotSidebar, ViewMode } from '@/components/CopilotSidebar';
import { CompareView } from '@/components/CompareView';
import { SidebarNavigator } from '@/components/SidebarNavigator';
import { useRunOrchestration } from '@/hooks/useRunOrchestration';

export default function Home() {
  const [viewMode, setViewMode] = useState<ViewMode>('AWS');
  const {
    runStatus,
    activeNodes,
    completedNodes,
    messages,
    setMessages,
    architectureResult,
    studioUrl,
    startRun,
  } = useRunOrchestration();

  return (
    <div className="flex h-screen w-full overflow-hidden bg-slate-50">
      {/* Left Sidebar Navigator */}
      <SidebarNavigator viewMode={viewMode} setViewMode={setViewMode} />

      {/* Main Content Area */}
      <main
        className={`flex flex-1 overflow-hidden ${viewMode === 'Compare' ? 'flex-col' : 'flex-row'}`}
      >
        {viewMode === 'Compare' ? (
          <>
            <div className="flex-1 relative overflow-hidden flex flex-col">
              <div className="p-6 pb-0 z-10 bg-slate-50">
                <h2 className="text-2xl font-bold text-slate-800">
                  Compare Solutions
                </h2>
                <p className="text-sm text-slate-500 mt-1 max-w-2xl leading-relaxed">
                  Side-by-side comparison of the proposed AWS and Azure
                  architectures.
                </p>
              </div>
              <CompareView awsResult={architectureResult} azureResult={null} />
            </div>
            <CopilotSidebar
              provider={viewMode}
              variant="bottom"
              onRunStart={startRun}
              runStatus={runStatus}
              messages={messages}
              setMessages={setMessages}
              studioUrl={studioUrl}
            />
          </>
        ) : (
          <>
            {/* Main Content Area - Graph */}
            <div className="flex-1 h-full relative flex flex-col">
              {/* Header Overlay */}
              <div className="absolute top-0 left-0 right-0 p-6 z-10 pointer-events-none">
                <h2 className="text-2xl font-bold text-slate-800">
                  {viewMode} Architecture
                </h2>
                <p className="text-sm text-slate-500 mt-1 max-w-2xl leading-relaxed">
                  An agentic AI framework using LangGraph to automate and
                  validate complex cloud architectures via a recursive
                  Evaluator-Optimizer pattern.
                </p>
              </div>

              {/* Graph Container */}
              <div className="w-full h-full">
                <WorkflowGraph
                  provider={viewMode}
                  activeNodes={activeNodes}
                  completedNodes={completedNodes}
                  runStatus={runStatus}
                />
              </div>
            </div>

            {/* Right Sidebar - Copilot */}
            <CopilotSidebar
              provider={viewMode}
              variant="sidebar"
              onRunStart={startRun}
              runStatus={runStatus}
              messages={messages}
              setMessages={setMessages}
              studioUrl={studioUrl}
            />
          </>
        )}
      </main>
    </div>
  );
}
