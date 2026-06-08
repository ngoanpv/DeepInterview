import { NextResponse, type NextRequest } from "next/server";
import { createClient } from "@/lib/supabase/server";

/**
 * Sign the user out, then redirect home. No-op on the auth side when Supabase
 * is unconfigured (dev mode) — still redirects so the button always works.
 */
export async function POST(request: NextRequest) {
  const supabase = await createClient();
  if (supabase) {
    await supabase.auth.signOut();
  }
  return NextResponse.redirect(new URL("/", request.url), { status: 303 });
}
