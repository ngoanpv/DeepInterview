import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));

import { createInterviewToken } from "../lib/livekit";

const KEYS = [
  "LIVEKIT_URL",
  "LIVEKIT_API_KEY",
  "LIVEKIT_API_SECRET",
  "LIVEKIT_AGENT_NAME",
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

function setLiveKitEnv(agentName?: string) {
  process.env.LIVEKIT_URL = "wss://test.livekit.cloud";
  process.env.LIVEKIT_API_KEY = "devkey";
  process.env.LIVEKIT_API_SECRET = "secretsecretsecretsecretsecretsecret";
  if (agentName === undefined) delete process.env.LIVEKIT_AGENT_NAME;
  else process.env.LIVEKIT_AGENT_NAME = agentName;
}

function decodePayload(jwt: string): Record<string, unknown> {
  return JSON.parse(
    Buffer.from(jwt.split(".")[1] ?? "", "base64").toString(),
  ) as Record<string, unknown>;
}

afterEach(restore);

describe("createInterviewToken explicit agent dispatch (issue #67)", () => {
  it("requests the interviewer worker via roomConfig.agents with the session id", async () => {
    snapshot();
    setLiveKitEnv();

    const { token, url } = await createInterviewToken({
      room: "sess_123",
      identity: "dev-sess_123",
    });

    expect(url).toBe("wss://test.livekit.cloud");
    const payload = decodePayload(token);
    const roomConfig = payload.roomConfig as {
      agents: { agentName: string; metadata: string }[];
    };
    expect(roomConfig.agents).toHaveLength(1);
    // Default dispatch name — must match the worker's agent_name default.
    expect(roomConfig.agents[0]?.agentName).toBe(
      "deepinterview-interviewer",
    );
    expect(JSON.parse(roomConfig.agents[0]?.metadata ?? "{}")).toEqual({
      session_id: "sess_123",
    });
    // Room grant still pins the token to exactly this session's room.
    expect((payload.video as { room: string }).room).toBe("sess_123");
  });

  it("honors LIVEKIT_AGENT_NAME so web and worker stay in sync", async () => {
    snapshot();
    setLiveKitEnv("custom-interviewer");

    const { token } = await createInterviewToken({
      room: "sess_abc",
      identity: "user-1",
    });

    const payload = decodePayload(token);
    const roomConfig = payload.roomConfig as {
      agents: { agentName: string; metadata: string }[];
    };
    expect(roomConfig.agents[0]?.agentName).toBe("custom-interviewer");
    expect(JSON.parse(roomConfig.agents[0]?.metadata ?? "{}")).toEqual({
      session_id: "sess_abc",
    });
  });
});
