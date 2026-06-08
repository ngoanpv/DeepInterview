import type { NextRequest } from "next/server";
import { updateSession } from "@/lib/supabase/middleware";

export async function proxy(request: NextRequest) {
  return updateSession(request);
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (build assets)
     * - _next/image (image optimizer)
     * - favicon.ico
     * - api/health (WP-0 health check, no session needed)
     */
    "/((?!_next/static|_next/image|favicon.ico|api/health).*)",
  ],
};
