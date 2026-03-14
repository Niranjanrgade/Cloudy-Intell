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
