/**
 * POST /api/threads — Create a new LangGraph thread.
 *
 * A LangGraph thread is a session container that holds the graph state across
 * invocations.  Each architecture generation run gets its own thread.  The
 * thread ID is used for:
 * - Checkpointing state between graph nodes.
 * - Linking to LangGraph Studio for real-time run observation.
 * - Fetching the final state after the run completes.
 *
 * Returns: `{ thread_id: string }`
 */
import { NextResponse } from 'next/server';
import { getLanggraphClient } from '@/lib/langgraph-client';

export async function POST() {
  try {
    const client = getLanggraphClient();
    const thread = await client.threads.create();
    return NextResponse.json({ thread_id: thread.thread_id });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Failed to create thread';
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
