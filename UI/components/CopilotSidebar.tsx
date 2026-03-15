/**
 * CopilotSidebar — Chat interface for CloudyIntel.
 *
 * This component provides the conversational UI where users describe their
 * cloud architecture problem and receive real-time status updates as the
 * LangGraph agents work.  Features:
 *
 * - **Message display**: Shows user messages, assistant responses, and
 *   per-node status updates (e.g. "Compute Architect — designing compute layer").
 * - **Input handling**: Text input with Enter-to-send and button submission.
 *   Disabled while a run is in progress.
 * - **LangGraph Studio link**: External link button to open the active run
 *   in LangGraph Studio for detailed observation.
 * - **Provider context switching**: Automatically appends a context-switch
 *   message when the user changes providers (AWS/Azure/Compare).
 * - **Layout variants**: Supports both sidebar (right panel) and bottom
 *   (horizontal) layouts for different view modes.
 * - **Auto-scroll**: Scrolls to the latest message as new updates arrive.
 */
'use client';

import { useState, useRef, useEffect, Dispatch, SetStateAction } from 'react';
import { Send, Bot, User, Sparkles, X, Loader2, Activity, ExternalLink } from 'lucide-react';
import type { RunStatus, ChatMessage } from '@/lib/types';

export type ViewMode = 'AWS' | 'Azure' | 'Compare';

interface CopilotSidebarProps {
  provider: ViewMode;
  variant?: 'sidebar' | 'bottom';
  onRunStart: (problem: string) => Promise<void>;
  runStatus: RunStatus;
  messages: ChatMessage[];
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>;
  studioUrl?: string | null;
}

export function CopilotSidebar({
  provider,
  variant = 'sidebar',
  onRunStart,
  runStatus,
  messages,
  setMessages,
  studioUrl,
}: CopilotSidebarProps) {
  const [isOpen, setIsOpen] = useState(true);
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // When provider changes, append a context-switch message
  const prevProviderRef = useRef(provider);
  useEffect(() => {
    if (provider !== prevProviderRef.current) {
      prevProviderRef.current = provider;
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          role: 'assistant',
          content: `Switched context to ${provider}. ${provider === 'Compare' ? 'I am ready to compare AWS and Azure architectures side-by-side.' : `I am ready to design and validate ${provider} architectures.`} What would you like to build?`,
        },
      ]);
    }
  }, [provider, setMessages]);

  // Auto-scroll when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim() || runStatus === 'running') return;
    const problem = input.trim();
    setInput('');
    onRunStart(problem);
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 p-4 bg-indigo-600 text-white rounded-full shadow-lg hover:bg-indigo-700 transition-all z-50 flex items-center justify-center"
      >
        <Sparkles className="w-6 h-6" />
      </button>
    );
  }

  const containerClasses =
    variant === 'sidebar'
      ? 'w-96 bg-white border-l border-slate-200 shadow-2xl flex flex-col h-full z-40 transition-all duration-300 ease-in-out'
      : 'w-full h-72 bg-white border-t border-slate-200 shadow-2xl flex flex-col z-40 transition-all duration-300 ease-in-out';

  return (
    <div className={containerClasses}>
      {/* Header */}
      <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-indigo-50/50">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-indigo-100 rounded-lg text-indigo-600">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <h2 className="font-semibold text-slate-800 text-sm">
              CloudyIntel Copilot
            </h2>
            <p className="text-xs text-slate-500">
              Cloud Solution Architect Assistant
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {studioUrl && (
            <a
              href={studioUrl}
              target="_blank"
              rel="noopener noreferrer"
              title="View in LangGraph Studio"
              className="p-2 text-indigo-500 hover:text-indigo-700 hover:bg-indigo-50 rounded-md transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
            </a>
          )}
          <button
            onClick={() => setIsOpen(false)}
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-md transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50/50">
        {messages.map((msg) =>
          msg.role === 'status' ? (
            <div
              key={msg.id}
              className="flex items-center gap-2 text-xs text-slate-500 px-2 py-1"
            >
              <Activity className="w-3 h-3 text-indigo-400 animate-pulse" />
              <span>{msg.content}</span>
            </div>
          ) : (
            <div
              key={msg.id}
              className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}
            >
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                  msg.role === 'user'
                    ? 'bg-slate-800 text-white'
                    : 'bg-indigo-100 text-indigo-600'
                }`}
              >
                {msg.role === 'user' ? (
                  <User className="w-4 h-4" />
                ) : (
                  <Bot className="w-4 h-4" />
                )}
              </div>
              <div
                className={`px-4 py-3 rounded-2xl max-w-[80%] text-sm whitespace-pre-wrap ${
                  msg.role === 'user'
                    ? 'bg-slate-800 text-white rounded-tr-sm'
                    : 'bg-white border border-slate-200 text-slate-700 rounded-tl-sm shadow-sm'
                }`}
              >
                {msg.content}
                {msg.link && (
                  <a
                    href={msg.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-2 flex items-center gap-1.5 text-xs font-medium text-indigo-600 hover:text-indigo-800 transition-colors"
                  >
                    <ExternalLink className="w-3 h-3" />
                    Open in LangGraph Studio
                  </a>
                )}
              </div>
            </div>
          ),
        )}

        {/* Typing indicator while running */}
        {runStatus === 'running' && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-indigo-100 text-indigo-600">
              <Bot className="w-4 h-4" />
            </div>
            <div className="px-4 py-3 rounded-2xl bg-white border border-slate-200 text-slate-500 rounded-tl-sm shadow-sm flex items-center gap-2 text-sm">
              <Loader2 className="w-4 h-4 animate-spin" />
              Agents working...
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-slate-100 bg-white">
        <div className="relative flex items-center max-w-4xl mx-auto">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder={
              runStatus === 'running'
                ? 'Agents are working...'
                : 'Describe your cloud architecture problem...'
            }
            disabled={runStatus === 'running'}
            className="w-full pl-4 pr-12 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || runStatus === 'running'}
            className="absolute right-2 p-2 text-indigo-600 disabled:text-slate-300 hover:bg-indigo-50 rounded-lg transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <div className="mt-2 text-center">
          <p className="text-[10px] text-slate-400">
            Powered by LangGraph
          </p>
        </div>
      </div>
    </div>
  );
}
