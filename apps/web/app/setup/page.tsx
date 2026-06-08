import Link from "next/link";
import { isR2Configured, isSupabaseConfigured } from "@/lib/env";
import { getUser } from "@/lib/supabase/server";
import { Eyebrow } from "@/components/ui/eyebrow";
import { Button } from "@/components/ui/button";
import { LanguageToggle } from "@/components/language-toggle";
import { SetupForm } from "@/components/setup/setup-form";

// Evaluate at request time: `isR2Configured()` reads server env, which must not
// be baked into a static prerender (a deploy with R2 set would otherwise serve a
// stale `r2Configured=false` and never light the upload path).
export const dynamic = "force-dynamic";

/**
 * Setup is a server component so it can read server-only config
 * (`isR2Configured()` is invisible to the browser) and resolve the current
 * user, then hand both into the client form island as props.
 */
export default async function SetupPage() {
  // R2 status must be computed server-side — the client can't see server env.
  const r2Configured = isR2Configured();

  // Soft auth signal: surfaces a sign-out affordance when signed in. Page-level
  // gating lives on /interview; setup itself stays reachable in dev mode.
  const user = isSupabaseConfigured() ? await getUser() : null;

  return (
    <main className="mx-auto max-w-[720px] px-6 py-12">
      <header className="flex items-center justify-between">
        <Link href="/" className="no-underline">
          <Eyebrow>DeepInterview</Eyebrow>
        </Link>
        <div className="flex items-center gap-3">
          <LanguageToggle />
          {user && (
            <form action="/auth/signout" method="post">
              <Button type="submit" variant="ghost" size="sm">
                Sign out
              </Button>
            </form>
          )}
        </div>
      </header>

      <SetupForm r2Configured={r2Configured} />
    </main>
  );
}
