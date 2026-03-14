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
