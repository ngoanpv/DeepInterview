import { serverEnv } from "@/lib/env";

export const dynamic = "force-dynamic";

/**
 * Proxy for the agent's local saved resume + JD library (`GET /api/sessions/library`).
 * Only enabled when the agent runs on the local SQLite store; returns empty lists otherwise.
 */
export async function GET() {
  try {
    const res = await fetch(`${serverEnv.agentApiUrl}/api/sessions/library`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5_000),
    });
    if (!res.ok) return Response.json({ resumes: [], jobs: [] });
    return Response.json(await res.json());
  } catch {
    return Response.json({ resumes: [], jobs: [] });
  }
}
