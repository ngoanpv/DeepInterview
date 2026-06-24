import { NextResponse } from "next/server";
import { z } from "zod";
import {
  KbQueryResponseSchema,
  LanguageSchema,
  type KbQueryResponse,
} from "@deepinterview/shared";
import { gateRequest } from "@deepinterview/ee";
import { getUser } from "@/lib/supabase/server";

// Reads server-only env (LIGHTRAG_URL) and the per-request user; never prerender.
export const dynamic = "force-dynamic";

/**
 * Incoming client body. We do NOT validate with the shared `KbQueryRequestSchema`
 * here: that names the store key `user_id`, but the OSS flow is auth-free and
 * keys the knowledge store by `session_id` (the same key the prep pipeline
 * ingests under and the Study Coach retrieves with). The client sends
 * `{session_id?, query, lang}`; `session_id` defaults to "anonymous" and `lang`
 * falls back to "en".
 */
const BodySchema = z.object({
  session_id: z.string().default("anonymous"),
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
  // Resolve the user server-side; anonymous when there's no session. The
  // distribution gate (no-op in OSS) runs before any work — including the
  // offline mock — so required-auth distributions are consistent here.
  const user = await getUser();
  const gate = gateRequest({
    pathname: "/api/kb/query",
    isAuthenticated: Boolean(user),
  });
  if (!gate.allow) {
    return NextResponse.json({ error: "Sign in required" }, { status: 401 });
  }

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

  try {
    const upstream = await fetch(`${lightragUrl.replace(/\/$/, "")}/kb/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // Scope retrieval by session_id — the key the prep pipeline ingested
      // under and the agent coach queries with — so the docs are reachable.
      body: JSON.stringify({
        user_id: body.session_id,
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
