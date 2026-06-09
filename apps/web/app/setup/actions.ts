"use server";

import type { PrepRequest } from "@deepinterview/shared";
import { requestPrep } from "@/lib/api";
import { createClient, getUser } from "@/lib/supabase/server";
import { isSupabaseConfigured } from "@/lib/env";
import {
  canStartInterview,
  shouldUseCredit,
  type ProfileBilling,
} from "@/lib/plan";

export type StartSessionResult =
  | { ok: true; session_id: string }
  // `error` stays required (existing consumers read `result.error`); `reason`
  // is an additive discriminator the client uses to route to /pricing.
  | { ok: false; error: string; reason?: "out_of_interviews" };

/**
 * Kick off the prep pipeline and return the new session id. We return
 * `{session_id}` (rather than redirect()) so the client owns navigation via
 * router.push — this also keeps the Next 15 redirect-in-action pitfall out of
 * the picture. When Supabase is configured we require a signed-in user; offline
 * (dev mode) we proceed without auth.
 *
 * Gating (WP-11, golden rule 5): when Supabase is configured we enforce the
 * per-tier voice-interview cap BEFORE spending any prep compute. Offline/dev has
 * no profile store, so the gate is bypassed (unlimited local dev).
 */
export async function startSession(
  input: PrepRequest,
): Promise<StartSessionResult> {
  const configured = isSupabaseConfigured();

  // Resolved only in the configured path; reused after a successful prep to
  // draw down the metered cap or a credit.
  let supabase: Awaited<ReturnType<typeof createClient>> = null;
  let userId: string | null = null;
  let profile: ProfileBilling | null = null;

  if (configured) {
    const user = await getUser();
    if (!user) {
      return { ok: false, error: "Please sign in to start an interview." };
    }
    userId = user.id;
    supabase = await createClient();

    // Load the billing-relevant profile row and roll the monthly period if due.
    if (supabase) {
      await supabase.rpc("reset_usage_if_due", { p_user_id: userId });
      const { data } = await supabase
        .from("profiles")
        .select("plan, interviews_used, credits")
        .eq("id", userId)
        .maybeSingle();
      profile = (data as ProfileBilling | null) ?? {
        plan: "free",
        interviews_used: 0,
        credits: 0,
      };

      // GOLDEN RULE 5: enforce the cap before any interview is created.
      const gate = canStartInterview(profile);
      if (!gate.allowed) {
        return {
          ok: false,
          error:
            "You've used all your interviews for this period. Upgrade or buy credits to continue.",
          reason: gate.reason,
        };
      }
    }
  }

  let session_id: string;
  try {
    // Forward the signed-in user's id so the agent stamps it on the `sessions`
    // row (sessions.user_id). Without this the row is unowned (NULL) and the
    // report's RLS read (auth.uid() = user_id) can never see it, so the page
    // falls back to sample data. Offline/dev has no user → omit it.
    ({ session_id } = await requestPrep({
      ...input,
      user_id: userId ?? undefined,
    }));
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Could not reach the prep service.";
    return { ok: false, error: message };
  }

  // Interview created → draw it down. Prefer the metered cap; spend a credit
  // only once the cap is exhausted. Best-effort: a metering failure must not
  // strand a user who already has a session (the gate already protected margin).
  if (configured && supabase && userId && profile) {
    try {
      if (shouldUseCredit(profile)) {
        const nextCredits = Math.max(0, (profile.credits ?? 0) - 1);
        await supabase
          .from("profiles")
          .update({ credits: nextCredits })
          .eq("id", userId);
        await supabase.from("credit_ledger").insert({
          user_id: userId,
          delta: -1,
          reason: "interview_overage",
        });
      } else {
        await supabase
          .from("profiles")
          .update({ interviews_used: (profile.interviews_used ?? 0) + 1 })
          .eq("id", userId);
      }
    } catch {
      // Swallow: the session exists; metering will reconcile on next load.
    }
  }

  return { ok: true, session_id };
}
