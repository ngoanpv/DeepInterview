import { NextResponse } from "next/server";
import { createClient as createSupabaseAdmin } from "@supabase/supabase-js";
import { isPaddleWebhookConfigured } from "@/lib/billing";
import { verifyPaddleWebhook } from "@/lib/billing-server";
import { serverEnv } from "@/lib/env";
import { normalizePlan } from "@/lib/plan";

/**
 * Paddle Billing webhook (WP-11).
 *
 * Status contract:
 *   501 — Paddle webhook secret not configured (feature off).
 *   400 — signature missing/invalid, or unparseable body.
 *   200 — accepted (handled, or an event type we intentionally ignore).
 *
 * All Supabase writes use a service-role client built LAZILY inside the handler
 * (never at module top-level) so the route imports cleanly with no env. Service
 * role bypasses RLS — the new tables have no client write policies by design.
 */

export const dynamic = "force-dynamic";

type PaddleEvent = {
  event_type?: string;
  data?: Record<string, unknown>;
};

/** Service-role admin client, or null when service env is incomplete. */
function adminClient() {
  const url = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = serverEnv.supabaseServiceRoleKey;
  if (!url || !key) return null;
  return createSupabaseAdmin(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

function asString(v: unknown): string | undefined {
  return typeof v === "string" ? v : undefined;
}

function customDataUserId(
  data: Record<string, unknown> | undefined,
): string | undefined {
  const cd = data?.custom_data as Record<string, unknown> | undefined;
  return asString(cd?.user_id);
}

export async function POST(request: Request) {
  // Feature gate: no secret → not enabled.
  if (!isPaddleWebhookConfigured()) {
    return NextResponse.json(
      { error: "Billing webhook not configured" },
      { status: 501 },
    );
  }

  const raw = await request.text();
  const signature = request.headers.get("paddle-signature");

  if (!verifyPaddleWebhook(signature, raw)) {
    return NextResponse.json({ error: "Invalid signature" }, { status: 400 });
  }

  let event: PaddleEvent;
  try {
    event = JSON.parse(raw) as PaddleEvent;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const supabase = adminClient();
  if (!supabase) {
    // Verified but we can't persist — surface as a server-config problem.
    return NextResponse.json(
      { error: "Supabase service role not configured" },
      { status: 501 },
    );
  }

  const type = event.event_type ?? "";
  const data = event.data;
  const userId = customDataUserId(data);

  try {
    switch (type) {
      case "subscription.created":
      case "subscription.updated": {
        if (!userId) break;
        const subId = asString(data?.id) ?? `sub_${userId}`;
        const status = asString(data?.status) ?? "active";
        // Map the priced item back to a plan; fall back to "pro".
        const plan = normalizePlan(planFromSubscription(data) ?? "pro");
        await supabase.from("subscriptions").upsert({
          id: subId,
          user_id: userId,
          plan,
          status,
          provider: "paddle",
          updated_at: new Date().toISOString(),
        });
        // Active/trialing → reflect the plan on the profile; otherwise downgrade.
        const activePlan = ["active", "trialing"].includes(status)
          ? plan
          : "free";
        await supabase
          .from("profiles")
          .update({ plan: activePlan })
          .eq("id", userId);
        break;
      }

      case "subscription.canceled": {
        if (!userId) break;
        const subId = asString(data?.id);
        if (subId) {
          await supabase
            .from("subscriptions")
            .update({
              status: "canceled",
              updated_at: new Date().toISOString(),
            })
            .eq("id", subId);
        }
        await supabase
          .from("profiles")
          .update({ plan: "free" })
          .eq("id", userId);
        break;
      }

      case "transaction.completed": {
        // One-off purchase (credit pack or lifetime). Grant credits when the
        // purchased item carries a credit grant in custom_data.
        if (!userId) break;
        const grant = creditGrantFromTransaction(data);
        if (grant > 0) {
          const { data: row } = await supabase
            .from("profiles")
            .select("credits")
            .eq("id", userId)
            .maybeSingle();
          const current = (row?.credits as number | undefined) ?? 0;
          await supabase
            .from("profiles")
            .update({ credits: current + grant })
            .eq("id", userId);
          await supabase
            .from("credit_ledger")
            .insert({ user_id: userId, delta: grant, reason: "pack_purchase" });
        }
        break;
      }

      default:
        // Unhandled event type — acknowledge so Paddle stops retrying.
        break;
    }
  } catch (err) {
    // Persisting failed — return 500 so Paddle retries the (verified) event.
    const message = err instanceof Error ? err.message : "handler error";
    return NextResponse.json({ error: message }, { status: 500 });
  }

  return NextResponse.json({ received: true }, { status: 200 });
}

/** Read a plan hint from custom_data; null if absent. */
function planFromSubscription(
  data: Record<string, unknown> | undefined,
): string | null {
  const cd = data?.custom_data as Record<string, unknown> | undefined;
  return asString(cd?.plan) ?? null;
}

/** Read a credit grant amount from custom_data (set when creating checkout). */
function creditGrantFromTransaction(
  data: Record<string, unknown> | undefined,
): number {
  const cd = data?.custom_data as Record<string, unknown> | undefined;
  const raw = cd?.credits;
  const n = typeof raw === "number" ? raw : Number(raw);
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : 0;
}
