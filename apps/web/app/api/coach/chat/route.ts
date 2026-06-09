import { NextResponse } from "next/server";
import { z } from "zod";
import {
  CoachReplySchema,
  LanguageSchema,
  type CoachReply,
} from "@deepinterview/shared";
import { serverEnv } from "@/lib/env";

// Reads server-only config (AGENT_API_URL) and proxies a live agent call.
export const dynamic = "force-dynamic";

/**
 * Client body. session_id is optional (the /prep surface may have no live
 * session); it only scopes knowledge retrieval. lang falls back to "en".
 */
const BodySchema = z.object({
  session_id: z.string().default("anonymous"),
  query: z.string().min(1),
  lang: LanguageSchema.catch("en").default("en"),
});

/** A grounded mock reply so the coach chat works even with the agent down. */
function mockReply(query: string): CoachReply {
  const q = query.trim().replace(/\s+/g, " ");
  return {
    answer:
      `Here's how I'd coach you on "${q}": name the framework, walk one concrete ` +
      `example end to end, then state the trade-off you're optimizing for. ` +
      `(Sample response — start the agent API for fully grounded coaching.)`,
    citations: [
      {
        title: "Prep notes",
        url: "https://example.com/kb/prep-notes",
        snippet: "Relevant guidance for this topic from your materials.",
      },
    ],
    follow_ups: [
      "Can you give a concrete example?",
      "What's a common mistake here?",
    ],
  };
}

export async function POST(request: Request) {
  let body: z.infer<typeof BodySchema>;
  try {
    body = BodySchema.parse(await request.json());
  } catch {
    return NextResponse.json(
      { error: "Invalid request body" },
      { status: 400 },
    );
  }

  try {
    const upstream = await fetch(`${serverEnv.agentApiUrl}/api/coach/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: body.session_id,
        query: body.query,
        lang: body.lang,
      }),
      // Don't let a slow agent hang the request forever.
      signal: AbortSignal.timeout(30_000),
    });

    if (!upstream.ok) return NextResponse.json(mockReply(body.query));

    const json = await upstream.json();
    const parsed = CoachReplySchema.safeParse(json);
    // Validate the upstream shape; fall back to a mock on drift.
    return NextResponse.json(
      parsed.success ? parsed.data : mockReply(body.query),
    );
  } catch {
    // Agent unreachable / timeout / bad JSON — stay resilient.
    return NextResponse.json(mockReply(body.query));
  }
}
