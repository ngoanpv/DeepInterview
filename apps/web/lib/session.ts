import { z } from "zod";
import { InterviewContextSchema, ScoreCardSchema } from "@deepinterview/shared";

/**
 * Client/server-shared view of a prep session as exposed by the agent
 * (`GET /api/session/{id}`) and proxied through our own
 * `GET /api/session/{id}` route.
 *
 * `progress` lists the COMPLETED step keys (order is non-deterministic and is a
 * subset of `PREP_STEPS`). `context` is only present once `status === "ready"`.
 */
export const SessionViewSchema = z.object({
  session_id: z.string(),
  // "no_answers": interview produced no answers; scoring was skipped and no
  // scorecard written, so the report shows an honest empty state (not zeros).
  status: z.enum([
    "prep",
    "ready",
    "rejected",
    "error",
    "complete",
    "no_answers",
  ]),
  progress: z.array(z.string()),
  prep_warnings: z.array(z.string()),
  context: InterviewContextSchema.nullable(),
  // Present once post-interview scoring has run; the report reads it from here
  // (via the agent API) so no Supabase/auth is needed on the read path.
  scorecard: ScoreCardSchema.nullish(),
});
export type SessionView = z.infer<typeof SessionViewSchema>;

/**
 * Client-side statuses layered on top of the wire contract by the poller:
 * - `not_found` — the agent 404'd this session repeatedly; it doesn't exist.
 * - `stalled`   — polling passed the overall deadline without reaching a
 *                 terminal status; show an error/retry state, don't spin forever.
 * Both are terminal (`!== "prep"`), so pollers stop on them.
 */
export type ClientSessionStatus =
  | SessionView["status"]
  | "not_found"
  | "stalled";
export type ClientSessionView = Omit<SessionView, "status"> & {
  status: ClientSessionStatus;
};

/** A prep step the agents run, with the user-facing label to render. */
export interface PrepStep {
  /** The key the agent emits into `progress` when this step completes. */
  key: string;
  /** Human label. `company_research` contains a `{company}` placeholder. */
  label: string;
}

/**
 * The five prep steps, in the order we display them. The agent reports
 * completion via `progress` (which may arrive in any order); we render in this
 * fixed order so the checklist reads top-to-bottom regardless.
 */
export const PREP_STEPS: readonly PrepStep[] = [
  { key: "cv_analysis", label: "Reading your CV" },
  { key: "jd_analysis", label: "Analyzing the job description" },
  { key: "company_research", label: "Researching {company}" },
  { key: "gap_matching", label: "Matching your fit" },
  { key: "question_planner", label: "Planning your interview" },
] as const;

/** Consecutive 404s before an unknown session is declared `not_found`. */
const NOT_FOUND_AFTER = 3;

/** Overall polling deadline; past it a still-pending session is `stalled`. */
const POLL_DEADLINE_MS = 15 * 60 * 1000;

/** Per-session poll bookkeeping (404 streak + when polling started). */
const pollStates = new Map<
  string,
  { startedAt: number; consecutive404: number }
>();

/** Restart the 404/deadline bookkeeping for a session (call from Retry UIs). */
export function resetSessionPolling(id: string): void {
  pollStates.delete(id);
}

/** A tolerant fallback view used on any error; status defaults to `prep`. */
function fallbackView(
  id: string,
  status: ClientSessionStatus = "prep",
): ClientSessionView {
  return {
    session_id: id,
    status,
    progress: [],
    prep_warnings: [],
    context: null,
    scorecard: null,
  };
}

/**
 * Fetch the session view from our proxy route. NEVER throws: any non-ok
 * response, parse drift, or network error resolves to a tolerant "still
 * preparing" view so the poller keeps showing the calm prep screen instead of
 * crashing (the agent may simply be down or mid-startup).
 *
 * Two honesty guards keep the poller from spinning forever:
 * - `NOT_FOUND_AFTER` consecutive 404s resolve to a terminal `not_found`
 *   (one 404 can be a race with session creation; a streak means it's real).
 * - past `POLL_DEADLINE_MS` of polling, a still-`prep` (or unreadable) view
 *   resolves to `stalled` so the UI can offer a retry instead of a spinner.
 */
export async function fetchSessionView(id: string): Promise<ClientSessionView> {
  let state = pollStates.get(id);
  if (!state) {
    state = { startedAt: Date.now(), consecutive404: 0 };
    pollStates.set(id, state);
  }
  const pastDeadline = Date.now() - state.startedAt > POLL_DEADLINE_MS;

  try {
    const res = await fetch(`/api/session/${encodeURIComponent(id)}`, {
      cache: "no-store",
    });

    // The proxy passes the agent's 404 through for unknown sessions.
    if (res.status === 404) {
      state.consecutive404 += 1;
      if (state.consecutive404 >= NOT_FOUND_AFTER) {
        return fallbackView(id, "not_found");
      }
      return fallbackView(id, pastDeadline ? "stalled" : "prep");
    }
    state.consecutive404 = 0;

    const json: unknown = await res.json();
    const parsed = SessionViewSchema.safeParse(json);
    if (parsed.success) {
      if (parsed.data.status === "prep" && pastDeadline) {
        return { ...parsed.data, status: "stalled" };
      }
      return parsed.data;
    }
    return fallbackView(id, pastDeadline ? "stalled" : "prep");
  } catch {
    return fallbackView(id, pastDeadline ? "stalled" : "prep");
  }
}
