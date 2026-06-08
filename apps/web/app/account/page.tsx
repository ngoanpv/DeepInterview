import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Eyebrow } from "@/components/ui/eyebrow";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { isSupabaseConfigured } from "@/lib/env";
import { createClient, getUser } from "@/lib/supabase/server";
import {
  PLANS,
  normalizePlan,
  planCap,
  remainingInterviews,
  type ProfileBilling,
} from "@/lib/plan";
import { AccountActions } from "./account-actions";

export const metadata: Metadata = {
  title: "Account — DeepInterview",
};

export const dynamic = "force-dynamic";

/**
 * Account / billing screen (WP-11). Auth-gated when Supabase is configured
 * (redirect to /login otherwise). Offline (dev) shows a representative preview
 * so the page renders with zero env.
 */
export default async function AccountPage() {
  if (!isSupabaseConfigured()) {
    return (
      <AccountView
        profile={{ plan: "free", interviews_used: 1, credits: 0 }}
        offline
      />
    );
  }

  const user = await getUser();
  if (!user) redirect("/login");

  const supabase = await createClient();
  let profile: ProfileBilling = {
    plan: "free",
    interviews_used: 0,
    credits: 0,
  };
  if (supabase) {
    await supabase.rpc("reset_usage_if_due", { p_user_id: user.id });
    const { data } = await supabase
      .from("profiles")
      .select("plan, interviews_used, credits")
      .eq("id", user.id)
      .maybeSingle();
    if (data) profile = data as ProfileBilling;
  }

  return <AccountView profile={profile} email={user.email ?? undefined} />;
}

function AccountView({
  profile,
  email,
  offline,
}: {
  profile: ProfileBilling;
  email?: string;
  offline?: boolean;
}) {
  const planId = normalizePlan(profile.plan);
  const plan = PLANS[planId];
  const cap = planCap(profile.plan);
  const used = Math.max(0, profile.interviews_used ?? 0);
  const credits = Math.max(0, profile.credits ?? 0);
  const remaining = remainingInterviews(profile);
  const usedInCap = Math.min(used, cap);

  return (
    <main className="mx-auto max-w-[760px] px-6 py-16">
      <Eyebrow>Account</Eyebrow>
      <h1 className="serif mt-4 text-4xl text-ink">Your plan</h1>
      {email && <p className="mt-2 text-[14px] text-muted">{email}</p>}
      {offline && (
        <p className="mt-4 rounded-[10px] border border-line bg-accent-soft px-3.5 py-3 text-[13px] text-ink-soft">
          Dev mode — Supabase is not configured, so this is a sample view.
          Connect Supabase to see real usage.
        </p>
      )}

      <Card className="mt-6 flex flex-col gap-6 p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="serif text-2xl text-ink">{plan.name}</span>
            {planId === "pro" && <Badge variant="accent">Pro</Badge>}
            {planId === "career" && <Badge variant="accent">Career</Badge>}
          </div>
          <Link href="/pricing" className="no-underline">
            <Button variant="ghost" size="sm">
              Compare plans
            </Button>
          </Link>
        </div>

        {/* Usage meter */}
        <div>
          <div className="flex items-baseline justify-between text-[13px]">
            <span className="text-muted">Interviews this period</span>
            <span className="text-ink">
              {usedInCap} / {cap} used
            </span>
          </div>
          <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-line">
            <div
              className="h-full rounded-full bg-accent"
              style={{
                width: `${cap > 0 ? Math.min(100, (usedInCap / cap) * 100) : 0}%`,
              }}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Stat
            label="Remaining"
            value={String(remaining)}
            hint="incl. credits"
          />
          <Stat label="Credits" value={String(credits)} hint="never expire" />
        </div>
      </Card>

      <div className="mt-8">
        <AccountActions plan={planId} />
      </div>
    </main>
  );
}

function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="rounded-[10px] border border-line bg-paper px-4 py-3">
      <p className="text-[12px] uppercase tracking-[0.08em] text-muted">
        {label}
      </p>
      <p className="serif mt-1 text-2xl text-ink">{value}</p>
      <p className="text-[12px] text-faint">{hint}</p>
    </div>
  );
}
