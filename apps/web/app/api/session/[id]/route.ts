import { NextResponse } from "next/server";
import { serverEnv } from "@/lib/env";

// Reads server-only config (AGENT_API_URL) and proxies a live agent call;
// never prerender / always run on the server per request.
export const dynamic = "force-dynamic";

/**
 * GET /api/session/[id] — server-side proxy to the agent's
 * `GET ${AGENT_API_URL}/api/session/{id}` (SessionView).
 *
 * We proxy (rather than call the agent from the browser) so `AGENT_API_URL`
 * stays server-only and CORS is a non-issue. On any fetch failure — agent down,
 * offline dev with no keys, timeout — we return a 503 with a prep-shaped body so
 * the client keeps showing the calm "preparing" view instead of crashing.
 *
 * Next 15: dynamic route `params` is a Promise.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  const preparing = {
    session_id: id,
    status: "prep" as const,
    progress: [] as string[],
    prep_warnings: [] as string[],
    context: null,
  };

  try {
    const upstream = await fetch(
      `${serverEnv.agentApiUrl}/api/session/${encodeURIComponent(id)}`,
      {
        method: "GET",
        headers: { accept: "application/json" },
        cache: "no-store",
        // Don't let a slow / hung agent block the poll forever.
        signal: AbortSignal.timeout(15_000),
      },
    );

    // Pass through the upstream JSON + status (incl. 404 for unknown sessions).
    const json = await upstream.json().catch(() => null);
    if (json === null) {
      return NextResponse.json(preparing, { status: 503 });
    }
    return NextResponse.json(json, { status: upstream.status });
  } catch {
    // Agent unreachable / timeout / bad body — stay in the preparing state.
    return NextResponse.json(preparing, { status: 503 });
  }
}
