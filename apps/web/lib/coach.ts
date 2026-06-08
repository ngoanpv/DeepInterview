import type { CoachReply, Citation, Language } from "@deepinterview/shared";

export type { CoachReply, Citation };

/**
 * Ask the Study Coach a question. Calls the `/api/coach/chat` Next route, which
 * proxies to the agent (and falls back to a mock when the agent is unreachable),
 * so this resolves to a grounded, synthesized answer + citations + follow-ups.
 * Client-safe: relative fetch only, no server env.
 */
export async function askCoach(
  query: string,
  lang: Language = "en",
  sessionId = "anonymous",
): Promise<CoachReply> {
  const res = await fetch("/api/coach/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, query, lang }),
  });

  if (!res.ok) {
    throw new Error(`Coach chat failed (${res.status})`);
  }

  return (await res.json()) as CoachReply;
}
