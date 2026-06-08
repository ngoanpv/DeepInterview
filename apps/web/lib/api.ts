import {
  PrepResponseSchema,
  ScoreResponseSchema,
  type PrepRequest,
  type PrepResponse,
  type ScoreRequest,
  type ScoreResponse,
} from "@deepinterview/shared";
import { serverEnv } from "@/lib/env";

async function postJson<T>(
  path: string,
  body: unknown,
  parse: (data: unknown) => T,
): Promise<T> {
  const res = await fetch(`${serverEnv.agentApiUrl}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(
      `Agent request ${path} failed: ${res.status} ${res.statusText}${
        text ? ` — ${text}` : ""
      }`,
    );
  }

  return parse(await res.json());
}

/** Kick off the prep pipeline for a CV + JD + company. */
export function requestPrep(body: PrepRequest): Promise<PrepResponse> {
  return postJson("/api/prep", body, (d) => PrepResponseSchema.parse(d));
}

/** Score a completed interview session. */
export function requestScore(body: ScoreRequest): Promise<ScoreResponse> {
  return postJson("/api/score", body, (d) => ScoreResponseSchema.parse(d));
}
