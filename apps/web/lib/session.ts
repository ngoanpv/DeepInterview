import { z } from "zod";
import { InterviewContextSchema } from "@deepinterview/shared";

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
  status: z.enum(["prep", "ready", "rejected", "error"]),
  progress: z.array(z.string()),
  prep_warnings: z.array(z.string()),
  context: InterviewContextSchema.nullable(),
});
export type SessionView = z.infer<typeof SessionViewSchema>;

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

/** A tolerant, still-preparing view used as the fallback on any error. */
function preparingFallback(id: string): SessionView {
  return {
    session_id: id,
    status: "prep",
    progress: [],
    prep_warnings: [],
    context: null,
  };
}

/**
 * Fetch the session view from our proxy route. NEVER throws: any non-ok
 * response, parse drift, or network error resolves to a tolerant "still
 * preparing" view so the poller keeps showing the calm prep screen instead of
 * crashing (the agent may simply be down or mid-startup).
 */
export async function fetchSessionView(id: string): Promise<SessionView> {
  try {
    const res = await fetch(`/api/session/${encodeURIComponent(id)}`, {
      cache: "no-store",
    });
    const json: unknown = await res.json();
    const parsed = SessionViewSchema.safeParse(json);
    if (parsed.success) return parsed.data;
    return preparingFallback(id);
  } catch {
    return preparingFallback(id);
  }
}
