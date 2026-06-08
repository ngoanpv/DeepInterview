import "server-only";
import { AccessToken } from "livekit-server-sdk";
import { isLiveKitConfigured, serverEnv } from "@/lib/env";

export interface CreateInterviewTokenArgs {
  /** LiveKit room name — we use the interview session id. */
  room: string;
  /** Participant identity (e.g. the user id, or a dev identity offline). */
  identity: string;
  /** Optional display name. */
  name?: string;
  /** Optional JSON-serializable metadata attached to the participant. */
  metadata?: Record<string, unknown>;
}

export interface InterviewToken {
  token: string;
  url: string;
}

/**
 * Mint a LiveKit access token granting a participant join+publish in `room`.
 *
 * Throws a clear error when LiveKit is not configured — call only behind an
 * `isLiveKitConfigured()` check (the token route does this). Never throws at import.
 */
export async function createInterviewToken({
  room,
  identity,
  name,
  metadata,
}: CreateInterviewTokenArgs): Promise<InterviewToken> {
  if (!isLiveKitConfigured()) {
    throw new Error(
      "LiveKit is not configured. Set LIVEKIT_URL, LIVEKIT_API_KEY and LIVEKIT_API_SECRET.",
    );
  }

  const at = new AccessToken(
    serverEnv.livekitApiKey,
    serverEnv.livekitApiSecret,
    {
      identity,
      name,
      metadata: metadata ? JSON.stringify(metadata) : undefined,
    },
  );

  at.addGrant({
    room,
    roomJoin: true,
    canPublish: true,
    canSubscribe: true,
    canPublishData: true,
  });

  const token = await at.toJwt();
  return { token, url: serverEnv.livekitUrl as string };
}
