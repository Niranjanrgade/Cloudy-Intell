/**
 * GET /api/threads/[threadId]/state — Fetch the final graph state.
 *
 * After a streaming run completes, the frontend calls this endpoint to retrieve
 * the complete final state from LangGraph.  This state contains the full
 * architecture result including:
 * - `architecture_components`: Per-domain component designs.
 * - `architecture_summary`: Polished final architecture document.
 * - `final_architecture`: Complete architecture artifact dict.
 * - `validation_summary`: Consolidated validation feedback.
 *
 * The state is used to populate the CompareView and display final results.
 */
import { NextRequest, NextResponse } from 'next/server';
import { getLanggraphClient } from '@/lib/langgraph-client';

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ threadId: string }> },
) {
  try {
    const { threadId } = await params;
    const client = getLanggraphClient();
    const state = await client.threads.getState(threadId);
    return NextResponse.json(state);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Failed to fetch state';
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
