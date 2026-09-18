import "server-only";
import {
  AccessToken,
  RoomAgentDispatch,
  RoomConfiguration,
} from "livekit-server-sdk";
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
 * The token carries an EXPLICIT agent dispatch (`roomConfig.agents`): the
 * voice worker registers under `LIVEKIT_AGENT_NAME` and LiveKit Cloud Agents
 * only routes a job to it when the token requests it. Without this the room
 * joins fine with no agent listening — the exact "Connecting your
 * interviewer…" hang in issue #67. The dispatch metadata carries the
 * session id so the worker can resolve its InterviewContext even when room
 * metadata is absent.
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

  // Explicit dispatch: route the interviewer worker into THIS room. `room`
  // IS the session id (interview page pins room = verified session id), and
  // the metadata lets the worker resolve it without depending on room
  // metadata being set. `livekitAgentName` must match the worker's
  // `agent_name` (LIVEKIT_AGENT_NAME) or the dispatch matches nothing.
  at.roomConfig = new RoomConfiguration({
    agents: [
      new RoomAgentDispatch({
        agentName: serverEnv.livekitAgentName,
        metadata: JSON.stringify({ session_id: room }),
      }),
    ],
  });

  const token = await at.toJwt();
  return { token, url: serverEnv.livekitUrl as string };
}
