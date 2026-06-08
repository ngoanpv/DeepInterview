import { redirect } from "next/navigation";
import { isSupabaseConfigured } from "@/lib/env";
import { getUser } from "@/lib/supabase/server";
import { PrepSummary } from "@/components/session/prep-summary";

// Page-level auth + a per-request agent poll downstream; never prerender.
export const dynamic = "force-dynamic";

/**
 * Prep screen shell (the step BETWEEN setup and the live interview). Server
 * component: gates auth, then hands the session id + chosen persona to the
 * `<PrepSummary>` client poller, which shows the agents working and then the
 * "what we found" bento.
 *
 * Next 15: `params`/`searchParams` are Promises — await them. Page-level auth:
 * when Supabase is configured and there's no user, redirect to /login; offline
 * (dev) we proceed without auth.
 */
export default async function SessionPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ persona?: string }>;
}) {
  const { id } = await params;
  const { persona } = await searchParams;

  if (isSupabaseConfigured()) {
    const user = await getUser();
    if (!user) redirect("/login");
  }

  return <PrepSummary sessionId={id} persona={persona ?? null} />;
}
