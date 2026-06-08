import { NextResponse } from "next/server";
import { z } from "zod";
import {
  KbQueryResponseSchema,
  LanguageSchema,
  type KbQueryResponse,
} from "@deepinterview/shared";
import { getUser } from "@/lib/supabase/server";

// Reads server-only env (LIGHTRAG_URL) and the per-request user; never prerender.
export const dynamic = "force-dynamic";

/**
 * Incoming client body. We do NOT validate with the shared `KbQueryRequestSchema`
 * here: that requires `user_id` (resolved server-side, not sent by the browser)
 * and a strict `LanguageSchema`. The client only sends `{query, lang}`; `lang`
 * falls back to "en" if absent/unsupported.
 */
const BodySchema = z.object({
  query: z.string().min(1),
  lang: LanguageSchema.catch("en").default("en"),
});

/** A grounded mock answer so the coach chat works fully offline. */
function mockAnswer(query: string): KbQueryResponse {
  const q = query.trim().replace(/\s+/g, " ");
  return {
    answer:
      `Here's a grounded take on "${q}": think in terms of the entities and ` +
      `relationships in your knowledge base. Anchor your answer in a concrete ` +
      `example, name the trade-off you're optimizing for, and cite where the ` +
      `claim comes from. (This is a sample response — connect the knowledge ` +
      `service to ground answers in your own notes and the company playbook.)`,
    citations: [
      {
        title: "Interviewing Patterns — STAR & system design",
        url: "https://example.com/kb/interviewing-patterns",
        snippet:
          "Open behavioral answers with Situation + Task; in design rounds, lead with capacity estimates before components.",
      },
      {
        title: "Company Playbook — what this team probes for",
        url: "https://example.com/kb/company-playbook",
        snippet:
          "Signals weighted highest: cross-team influence, exactly-once reasoning, and clear trade-off articulation.",
      },
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

  const lightragUrl = process.env.LIGHTRAG_URL;

  // Offline / unconfigured: return a grounded mock so the chat always works.
  if (!lightragUrl) {
    return NextResponse.json(mockAnswer(body.query));
  }

  // Resolve the user server-side; anonymous when there's no session.
  const user = await getUser();
  const userId = user?.id ?? "anonymous";

  try {
    const upstream = await fetch(`${lightragUrl.replace(/\/$/, "")}/kb/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: userId,
        query: body.query,
        lang: body.lang,
      }),
      // Don't let a slow RAG backend hang the request forever.
      signal: AbortSignal.timeout(30_000),
    });

    if (!upstream.ok) return NextResponse.json(mockAnswer(body.query));

    const json = await upstream.json();
    const parsed = KbQueryResponseSchema.safeParse(json);
    // Shape/validate upstream output; fall back to mock on drift.
    return NextResponse.json(
      parsed.success ? parsed.data : mockAnswer(body.query),
    );
  } catch {
    // Network error, timeout, bad JSON — stay resilient.
    return NextResponse.json(mockAnswer(body.query));
  }
}
