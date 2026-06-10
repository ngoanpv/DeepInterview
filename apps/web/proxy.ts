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
     * - API routes that never read auth cookies, where a refresh per request
     *   is pure waste — api/session is polled every ~1.2s by the prep screen:
     *   api/health, api/session, api/coach, api/upload, api/billing/webhook.
     * API routes that DO read auth cookies (api/token, api/kb) stay matched.
     */
    "/((?!_next/static|_next/image|favicon.ico|api/health|api/session|api/coach|api/upload|api/billing/webhook).*)",
  ],
};
