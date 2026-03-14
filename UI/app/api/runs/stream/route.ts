import { NextRequest } from 'next/server';
import { getLanggraphClient } from '@/lib/langgraph-client';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const {
      thread_id,
      user_problem,
      min_iterations = 1,
      max_iterations = 3,
    } = body as {
      thread_id: string;
      user_problem: string;
      min_iterations?: number;
      max_iterations?: number;
    };

    if (!thread_id || !user_problem) {
      return new Response(
        JSON.stringify({ error: 'thread_id and user_problem are required' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } },
      );
    }

    const client = getLanggraphClient();

    // Build initial input matching create_initial_state() from the backend
    const input = {
      messages: [{ role: 'human', content: user_problem }],
      user_problem,
      iteration_count: 0,
      min_iterations,
      max_iterations,
      architecture_domain_tasks: {},
      architecture_components: {},
      proposed_architecture: {},
      validation_feedback: [],
      validation_summary: null,
      audit_feedback: [],
      factual_errors_exist: false,
      design_flaws_exist: false,
      final_architecture: null,
      architecture_summary: null,
    };

    // Stream the run with "updates" mode so we see per-node state deltas
    const streamResponse = client.runs.stream(thread_id, 'cloudy-intell', {
      input,
      streamMode: ['updates'],
    });

    // Build a ReadableStream that forwards SSE events to the browser
    const encoder = new TextEncoder();
    const readable = new ReadableStream({
      async start(controller) {
        try {
          for await (const event of streamResponse) {
            const ssePayload = `data: ${JSON.stringify({ event: event.event, data: event.data })}\n\n`;
            controller.enqueue(encoder.encode(ssePayload));
          }
          // Signal stream end
          controller.enqueue(encoder.encode('data: [DONE]\n\n'));
          controller.close();
        } catch (err) {
          const msg = err instanceof Error ? err.message : 'Stream error';
          controller.enqueue(
            encoder.encode(`data: ${JSON.stringify({ event: 'error', data: { message: msg } })}\n\n`),
          );
          controller.close();
        }
      },
    });

    return new Response(readable, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Failed to start run';
    return new Response(JSON.stringify({ error: message }), {
      status: 502,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
