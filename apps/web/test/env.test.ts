import { afterEach, describe, expect, it } from "vitest";
import {
  isLiveKitConfigured,
  isR2Configured,
  isSupabaseConfigured,
  publicEnv,
  serverEnv,
} from "../lib/env";

const KEYS = [
  "NEXT_PUBLIC_SUPABASE_URL",
  "NEXT_PUBLIC_SUPABASE_ANON_KEY",
  "LIVEKIT_URL",
  "LIVEKIT_API_KEY",
  "LIVEKIT_API_SECRET",
  "LIVEKIT_AGENT_NAME",
  "R2_ACCOUNT_ID",
  "R2_ACCESS_KEY_ID",
  "R2_SECRET_ACCESS_KEY",
  "R2_BUCKET",
] as const;

const saved = new Map<string, string | undefined>();

function snapshot() {
  saved.clear();
  for (const k of KEYS) saved.set(k, process.env[k]);
}

function restore() {
  for (const k of KEYS) {
    const v = saved.get(k);
    if (v === undefined) delete process.env[k];
    else process.env[k] = v;
  }
}

function clearAll() {
  for (const k of KEYS) delete process.env[k];
}

afterEach(restore);

describe("provider-configured guards (offline-safe defaults)", () => {
  it("reports unconfigured when no keys are set", () => {
    snapshot();
    clearAll();
    expect(isSupabaseConfigured()).toBe(false);
    expect(isLiveKitConfigured()).toBe(false);
    expect(isR2Configured()).toBe(false);
  });

  it("reports configured only when every key for that provider is present", () => {
    snapshot();
    clearAll();
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://x.supabase.co";
    expect(isSupabaseConfigured()).toBe(false);
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = "anon";
    expect(isSupabaseConfigured()).toBe(true);
  });

  it("never throws at import/access time with zero keys (build-safe)", () => {
    snapshot();
    clearAll();
    expect(() => publicEnv.appUrl).not.toThrow();
    expect(publicEnv.appUrl).toBe("http://localhost:3000");
    expect(() => serverEnv.agentApiUrl).not.toThrow();
  });

  it("defaults the agent dispatch name so web and worker agree (issue #67)", () => {
    snapshot();
    clearAll();
    expect(serverEnv.livekitAgentName).toBe("deepinterview-interviewer");
    process.env.LIVEKIT_AGENT_NAME = "custom-interviewer";
    expect(serverEnv.livekitAgentName).toBe("custom-interviewer");
  });
});
