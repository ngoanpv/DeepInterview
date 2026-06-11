import type { NextRequest } from "next/server";
import { updateSession } from "@/lib/supabase/middleware";

export async function proxy(request: NextRequest) {
  return updateSession(request);
}

export const config = {
  matcher: [
    /*
     * Run the Supabase session refresh on PAGES — the documented SSR pattern
     * (server components can't write cookies, so the proxy refreshes the auth
     * token for them). Skip:
     * - _next/static (build assets)
     * - _next/image (image optimizer)
     * - favicon.ico
     * - API routes where a proxy refresh per request is pure waste —
     *   api/session is polled every ~1.2s by the prep screen and reads no
     *   auth; api/coach + api/upload resolve the user in-handler (route
     *   handlers can write cookies, so supabase-js refreshes the session
     *   itself) and self-gate via @deepinterview/ee; api/health and
     *   api/billing/webhook are identity-free:
     *   api/health, api/session, api/coach, api/upload, api/billing/webhook.
     * API routes that rely on the proxy refresh (api/token, api/kb) stay
     * matched. The distribution gate in updateSession applies to pages only;
     * API handlers self-gate with 401s.
     */
    "/((?!_next/static|_next/image|favicon.ico|api/health|api/session|api/coach|api/upload|api/billing/webhook).*)",
  ],
};
