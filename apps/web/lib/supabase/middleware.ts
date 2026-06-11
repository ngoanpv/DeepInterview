import { NextResponse, type NextRequest } from "next/server";
import { createServerClient } from "@supabase/ssr";
import { gateRequest } from "@deepinterview/ee";
import { isSupabaseConfigured, publicEnv } from "@/lib/env";

type CookieToSet = {
  name: string;
  value: string;
  options?: Record<string, unknown>;
};

/**
 * Refresh the Supabase auth session cookie on every matched request, then
 * consult the distribution gate (no-op in OSS).
 *
 * When Supabase is not configured the refresh is skipped, but the gate still
 * runs with `isAuthenticated: false` — a required-auth distribution must fail
 * CLOSED on missing/broken env, not silently serve everything. Do NOT insert
 * logic between `createServerClient` and `auth.getUser()` — the cookie
 * refresh depends on that ordering.
 */
export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });
  let isAuthenticated = false;

  if (isSupabaseConfigured()) {
    const supabase = createServerClient(
      publicEnv.supabaseUrl as string,
      publicEnv.supabaseAnonKey as string,
      {
        cookies: {
          getAll() {
            return request.cookies.getAll();
          },
          setAll(cookiesToSet: CookieToSet[]) {
            cookiesToSet.forEach(({ name, value }) =>
              request.cookies.set(name, value),
            );
            supabaseResponse = NextResponse.next({ request });
            cookiesToSet.forEach(({ name, value, options }) =>
              supabaseResponse.cookies.set(name, value, options),
            );
          },
        },
      },
    );

    // IMPORTANT: keep this immediately after client creation; refreshes the token.
    const { data } = await supabase.auth.getUser();
    isAuthenticated = Boolean(data.user);
  }

  // Distribution gate (no-op in OSS): pages only — API routes self-gate with
  // 401s in their handlers, a redirect-to-login is the wrong shape for them.
  const pathname = request.nextUrl.pathname;
  if (!pathname.startsWith("/api/")) {
    const gate = gateRequest({ pathname, isAuthenticated });
    if (!gate.allow) {
      const redirectResponse = NextResponse.redirect(
        new URL(gate.redirectTo ?? "/login", request.url),
      );
      // Carry any refreshed auth cookies over to the redirect.
      for (const cookie of supabaseResponse.cookies.getAll()) {
        redirectResponse.cookies.set(cookie);
      }
      return redirectResponse;
    }
  }

  return supabaseResponse;
}
