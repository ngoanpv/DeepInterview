import type {
  KbQueryResponse,
  Citation,
  Language,
} from "@deepinterview/shared";

export type { KbQueryResponse, Citation };

/**
 * Ask the study coach's knowledge base a question. Always resolves to a grounded
 * answer + citations: the `/api/kb/query` route proxies to LightRAG when it is
 * configured and otherwise returns a mock grounded answer, so this never throws
 * for offline/unconfigured callers.
 */
export async function queryKnowledge(
  query: string,
  lang: Language = "en",
  sessionId = "anonymous",
): Promise<KbQueryResponse> {
  const res = await fetch("/api/kb/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, query, lang }),
  });

  if (!res.ok) {
    throw new Error(`Knowledge query failed (${res.status})`);
  }

  return (await res.json()) as KbQueryResponse;
}
