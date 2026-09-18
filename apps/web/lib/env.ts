/**
 * Environment accessors. Read lazily — NEVER throw at import/build time so the
 * app builds and renders with zero configured keys (offline / provider-agnostic).
 *
 * Public values MUST use static `process.env.NEXT_PUBLIC_*` references so Next.js
 * can inline them into the browser bundle. Dynamic indexing is undefined client-side.
 */

/** Browser-safe public config. Inlined by Next at build time. */
export const publicEnv = {
  get supabaseUrl(): string | undefined {
    return process.env.NEXT_PUBLIC_SUPABASE_URL || undefined;
  },
  get supabaseAnonKey(): string | undefined {
    return process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || undefined;
  },
  get appUrl(): string {
    return process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";
  },
};

/** Server-only config. Never imported into client components. */
export const serverEnv = {
  get supabaseServiceRoleKey(): string | undefined {
    return process.env.SUPABASE_SERVICE_ROLE_KEY || undefined;
  },
  get livekitUrl(): string | undefined {
    return process.env.LIVEKIT_URL || undefined;
  },
  get livekitApiKey(): string | undefined {
    return process.env.LIVEKIT_API_KEY || undefined;
  },
  get livekitApiSecret(): string | undefined {
    return process.env.LIVEKIT_API_SECRET || undefined;
  },
  /**
   * Dispatch name the voice worker registers under (`agent_name`).
   * Must match the worker's `LIVEKIT_AGENT_NAME` so the token's explicit
   * `roomConfig.agents` dispatch actually routes to it (issue #67: without an
   * explicit dispatch the interviewer never joins — LiveKit reports the room
   * as healthy and the UI sits on "Connecting your interviewer…" forever).
   */
  get livekitAgentName(): string {
    return process.env.LIVEKIT_AGENT_NAME || "deepinterview-interviewer";
  },
  get r2AccountId(): string | undefined {
    return process.env.R2_ACCOUNT_ID || undefined;
  },
  get r2AccessKeyId(): string | undefined {
    return process.env.R2_ACCESS_KEY_ID || undefined;
  },
  get r2SecretAccessKey(): string | undefined {
    return process.env.R2_SECRET_ACCESS_KEY || undefined;
  },
  get r2Bucket(): string | undefined {
    return process.env.R2_BUCKET || undefined;
  },
  get r2PublicUrl(): string | undefined {
    return process.env.R2_PUBLIC_URL || undefined;
  },
  get agentApiUrl(): string {
    return process.env.AGENT_API_URL || "http://localhost:8000";
  },
  /** Shared secret for the agent API's guarded write endpoints (opt-in). */
  get internalApiSecret(): string | undefined {
    return process.env.INTERNAL_API_SECRET || undefined;
  },
  /** Shared secret for the LightRAG sidecar's guarded endpoints (opt-in). */
  get lightragApiSecret(): string | undefined {
    return process.env.LIGHTRAG_API_SECRET || undefined;
  },
};

/** True when both public Supabase keys are present (needed for auth). */
export function isSupabaseConfigured(): boolean {
  return Boolean(publicEnv.supabaseUrl && publicEnv.supabaseAnonKey);
}

/** True when LiveKit URL + API credentials are all present. */
export function isLiveKitConfigured(): boolean {
  return Boolean(
    serverEnv.livekitUrl &&
    serverEnv.livekitApiKey &&
    serverEnv.livekitApiSecret,
  );
}

/** True when all R2 credentials needed to presign an upload are present. */
export function isR2Configured(): boolean {
  return Boolean(
    serverEnv.r2AccountId &&
    serverEnv.r2AccessKeyId &&
    serverEnv.r2SecretAccessKey &&
    serverEnv.r2Bucket,
  );
}
