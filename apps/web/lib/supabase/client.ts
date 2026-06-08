import { createBrowserClient as createSsrBrowserClient } from "@supabase/ssr";
import { isSupabaseConfigured, publicEnv } from "@/lib/env";

/**
 * Browser Supabase client. Returns `null` when Supabase is not configured so
 * offline/dev rendering never crashes — callers guard on the null.
 */
export function createBrowserClient() {
  if (!isSupabaseConfigured()) return null;
  return createSsrBrowserClient(
    publicEnv.supabaseUrl as string,
    publicEnv.supabaseAnonKey as string,
  );
}
