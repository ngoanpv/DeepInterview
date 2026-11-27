import { serverEnv } from "@/lib/env";

export const dynamic = "force-dynamic";

/**
 * Proxy for the agent's local session listing (`GET /api/sessions`). The agent
 * only enables it for the single-user SQLite store; anywhere else it 404s and
 * we return an empty list so the UI falls back to browser-local history.
 */
export async function GET() {
  try {
    const res = await fetch(`${serverEnv.agentApiUrl}/api/sessions`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5_000),
    });
    if (!res.ok) return Response.json({ sessions: [] });
    return Response.json(await res.json());
  } catch {
    return Response.json({ sessions: [] });
  }
}
