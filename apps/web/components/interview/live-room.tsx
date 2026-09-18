"use client";

/**
 * <LiveRoom> — the WP-2 live interview screen orchestrator.
 *
 * Two strictly-separated paths share the SAME calm, centered layout:
 *
 *  • LIVE  (token && url): renders `<LiveKitRoom connect audio video={false}>`
 *    with `<RoomAudioRenderer/>` + `<StartAudio/>` and the hook-driven
 *    `<LiveSession/>`. Every LiveKit hook (useVoiceAssistant, useTranscriptions,
 *    useLocalParticipant, useConnectionState) lives ONLY inside
 *    that provider — `<LiveSession/>` is never rendered outside it.
 *
 *  • PREVIEW (no token): renders the identical layout from static sample data
 *    via `<PreviewSession/>`, which calls ZERO LiveKit hooks. This is the
 *    offline path the build runs with no env keys — the page renders fully.
 *
 * The room subtree is additionally gated behind a mounted flag so the
 * browser-only LiveKit client never runs during SSR/hydration.
 *
 * Failure UX (nothing fails silently):
 *  • Mic failure (permission denied / no device / device busy) → an assertive
 *    banner explains how to fix it; the room stays connected so the candidate
 *    can still hear the interviewer and type answers via the text fallback.
 *  • Connection lost (room error, server-side disconnect) → an honest
 *    "Connection lost" state with a Rejoin button that remounts the room.
 *  • Reconnecting (transient network blips) → a polite live-region notice.
 *  • A server-closed room (interview ended) routes to the report instead.
 */

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  StartAudio,
  useConnectionState,
  useLocalParticipant,
  useTranscriptions,
  useVoiceAssistant,
} from "@livekit/components-react";
import {
  ConnectionState,
  DisconnectReason,
  MediaDeviceFailure,
} from "livekit-client";
import "@livekit/components-styles";

import type { Persona } from "@/lib/personas";
import { cn } from "@/lib/cn";
import { useMessages } from "@/lib/i18n/client";
import { t, type Dictionary } from "@/lib/i18n";
import { VoiceStage, StagePreview } from "@/components/interview/voice-stage";
import {
  TranscriptPanel,
  type Turn,
} from "@/components/interview/transcript-panel";
import { ControlBar } from "@/components/interview/control-bar";
import { SessionTimer } from "@/components/interview/session-timer";
import { TextFallback } from "@/components/interview/text-fallback";

// The text-stream topic livekit-agents' RoomIO registers its chat handler on
// (TOPIC_CHAT in the Python SDK). Typed answers MUST go here to reach the agent.
const AGENT_CHAT_TOPIC = "lk.chat";

const SAMPLE_TURNS: Turn[] = [
  {
    id: "s1",
    role: "interviewer",
    text: "Thanks for joining. To start, walk me through a project you're proud of and the part you personally owned.",
  },
  {
    id: "s2",
    role: "candidate",
    text: "Sure. I led the migration of our checkout service off a monolith — I owned the rollout plan and the fallback path.",
  },
  {
    id: "s3",
    role: "interviewer",
    text: "What was the riskiest part of that rollout, and how did you de-risk it?",
  },
];

export interface LiveRoomProps {
  sessionId: string;
  persona: Persona;
  /** Null when LiveKit is unconfigured → preview (not-connected) mode. */
  token: string | null;
  url: string | null;
  /**
   * Why the preview path renders. `ended` = the session exists but is no
   * longer joinable (finished/errored) — the notice must say so, not blame
   * the LiveKit env. Defaults to `unconfigured`.
   */
  previewReason?: "unconfigured" | "ended";
}

/**
 * Human, fixable guidance for a microphone failure. Permission denial is the
 * common case — the browser blocked getUserMedia — so we say exactly where to
 * flip the switch instead of a generic "something went wrong".
 */
function describeMicFailure(
  messages: Dictionary,
  failure?: MediaDeviceFailure,
): string {
  switch (failure) {
    case MediaDeviceFailure.PermissionDenied:
      return t(messages, "interview.micBlocked");
    case MediaDeviceFailure.NotFound:
      return t(messages, "interview.micNotFound");
    case MediaDeviceFailure.DeviceInUse:
      return t(messages, "interview.micInUse");
    default:
      return t(messages, "interview.micUnknown");
  }
}

/**
 * Accessible failure banner for the scaffold's notice slot. `role="alert"` +
 * assertive aria-live so screen readers announce it the moment it appears.
 */
function ErrorNotice({
  title,
  message,
  action,
}: {
  title: string;
  message: string;
  action?: React.ReactNode;
}) {
  return (
    <div
      role="alert"
      aria-live="assertive"
      className={cn(
        "mx-auto mt-6 w-full max-w-xl rounded-card border border-accent/40",
        "bg-paper/80 px-4 py-3 text-center backdrop-blur-sm",
      )}
    >
      <p className="text-[13px] font-medium text-ink">{title}</p>
      <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">
        {message}
      </p>
      {action ? <div className="mt-3 flex justify-center">{action}</div> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Shared scaffold — both paths render this exact frame.               */
/* ------------------------------------------------------------------ */

function Scaffold({
  persona,
  stage,
  transcript,
  timer,
  controls,
  textFallback,
  notice,
}: {
  persona: Persona;
  stage: React.ReactNode;
  transcript: React.ReactNode;
  timer: React.ReactNode;
  controls: React.ReactNode;
  textFallback: React.ReactNode;
  notice?: React.ReactNode;
}) {
  return (
    <main className="relative min-h-screen overflow-hidden bg-paper">
      {/* Calm backdrop wash behind the frosted panels. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(110% 80% at 50% -10%, rgba(67,56,202,0.06), transparent 60%)",
        }}
      />

      <div className="relative mx-auto flex min-h-screen w-full max-w-5xl flex-col px-6 py-8">
        {/* Top row: who + the clock. */}
        <div className="flex items-center justify-between">
          <div className="flex flex-col">
            <span className="font-mono text-[10px] tracking-[0.16em] text-faint">
              DEEPINTERVIEW · LIVE
            </span>
            <span className="font-serif text-[17px] text-ink">
              {persona.name}
            </span>
          </div>
          {timer}
        </div>

        {/* Centerpiece: avatar + transcript, calm two-column on wide. */}
        <div className="mt-6 grid flex-1 items-center gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,420px)]">
          <div className="mx-auto w-full max-w-sm lg:max-w-md">{stage}</div>
          <div className="flex h-full max-h-[60vh] min-h-[280px] flex-col lg:max-h-[68vh]">
            {transcript}
          </div>
        </div>

        {notice}

        {/* Controls + accessible text fallback. */}
        <div className="mt-6 flex flex-col items-center gap-4">
          {controls}
          <div className="w-full max-w-xl">{textFallback}</div>
        </div>
      </div>
    </main>
  );
}

/* ------------------------------------------------------------------ */
/* LIVE session — descendant of <LiveKitRoom>; owns all LiveKit hooks. */
/* ------------------------------------------------------------------ */

/**
 * True when the room has been connected for `afterMs` and the agent has NEVER
 * joined it.
 *
 * The voice worker is a separate process (`docker compose --profile live up`),
 * so a correctly-configured browser can join a room that no agent is listening
 * on. LiveKit reports that as a perfectly healthy connection — the room is up,
 * the mic works, nothing errors — and the stage sits on "Connecting your
 * interviewer…" indefinitely with nothing to act on (issue #67).
 *
 * "Never" is deliberate: tracked with a ref so a mid-interview blip, or the
 * agent leaving at the end, can't retroactively raise a "didn't join" notice.
 */
function useAgentNeverJoined(
  connected: boolean,
  agentPresent: boolean,
  afterMs = 20_000,
) {
  const everJoined = React.useRef(false);
  const [waitedTooLong, setWaitedTooLong] = React.useState(false);

  if (agentPresent) everJoined.current = true;

  React.useEffect(() => {
    if (!connected || everJoined.current) return;
    const t = setTimeout(() => setWaitedTooLong(true), afterMs);
    return () => clearTimeout(t);
  }, [connected, afterMs]);

  return waitedTooLong && !everJoined.current;
}

function LiveSession({
  persona,
  sessionId,
  micError,
  onMicError,
}: {
  persona: Persona;
  sessionId: string;
  /** Mic-failure banner text — owned by <LiveRoom>, which also catches room-level capture failures. */
  micError: string | null;
  onMicError: (message: string | null) => void;
}) {
  const router = useRouter();
  const messages = useMessages();
  const connectionState = useConnectionState();
  const connected = connectionState === ConnectionState.Connected;
  const reconnecting =
    connectionState === ConnectionState.Reconnecting ||
    connectionState === ConnectionState.SignalReconnecting;

  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant();
  const transcriptions = useTranscriptions();
  // `disconnected` is what useVoiceAssistant reports while no agent participant
  // is in the room at all — the case the notice below explains.
  const { state: agentState } = useVoiceAssistant();
  const agentNeverJoined = useAgentNeverJoined(
    connected,
    agentState !== "disconnected",
  );

  const [ending, setEnding] = React.useState(false);

  // A publishing mic proves capture works again — clear any stale failure banner.
  React.useEffect(() => {
    if (isMicrophoneEnabled) onMicError(null);
  }, [isMicrophoneEnabled, onMicError]);

  // Typed answers bypass STT, so nothing in `transcriptions` ever carries
  // them — without a local echo the typed answer is invisible and the
  // interviewer appears to reply to nothing.
  const [typedTurns, setTypedTurns] = React.useState<
    { id: string; text: string; at: number }[]
  >([]);

  // Map streaming transcriptions + typed answers → turns, in send/receive
  // order. "You" when the segment belongs to the local participant, otherwise
  // the interviewer (agent / avatar worker). STT finalizes speech in short
  // segments, so consecutive segments from the same speaker are merged into
  // one turn — one paragraph per speaking turn, not a new "You" label per
  // sentence fragment.
  const turns: Turn[] = React.useMemo(() => {
    const localIdentity = localParticipant.identity;
    const entries: (Turn & { at: number })[] = [];
    for (const t of transcriptions) {
      const text = t.text.trim();
      if (!text) continue;
      entries.push({
        at: t.streamInfo.timestamp ?? 0,
        id: t.streamInfo.id,
        role:
          t.participantInfo.identity === localIdentity
            ? ("candidate" as const)
            : ("interviewer" as const),
        text,
      });
    }
    for (const t of typedTurns) {
      entries.push({ at: t.at, id: t.id, role: "candidate", text: t.text });
    }
    entries.sort((a, b) => a.at - b.at);
    const merged: Turn[] = [];
    for (const entry of entries) {
      const last = merged[merged.length - 1];
      if (last?.role === entry.role) {
        last.text = `${last.text} ${entry.text}`;
      } else {
        merged.push({ id: entry.id, role: entry.role, text: entry.text });
      }
    }
    return merged;
  }, [transcriptions, typedTurns, localParticipant.identity]);

  async function toggleMute() {
    try {
      await localParticipant.setMicrophoneEnabled(!isMicrophoneEnabled);
      onMicError(null);
    } catch (error) {
      // getUserMedia rejection: permission denied / no device / device busy.
      onMicError(
        describeMicFailure(messages, MediaDeviceFailure.getFailure(error)),
      );
    }
  }

  async function endInterview() {
    setEnding(true);
    try {
      await localParticipant.setMicrophoneEnabled(false);
    } catch {
      // best-effort; proceed to leave regardless
    }
    // The room disconnect happens as <LiveKitRoom> unmounts on navigation.
    router.push(`/report/${encodeURIComponent(sessionId)}`);
  }

  function sendText(text: string) {
    // Optimistic local echo — the agent does not stream typed input back.
    setTypedTurns((prev) => [
      ...prev,
      { id: `typed-${Date.now()}-${prev.length}`, text, at: Date.now() },
    ]);
    // Text streams on "lk.chat" are what the LiveKit agent's RoomIO consumes
    // (register_text_stream_handler(TOPIC_CHAT)). A raw data-channel publish on
    // a custom topic is never delivered to the agent — the typed answer would
    // silently vanish.
    void localParticipant
      .sendText(text, { topic: AGENT_CHAT_TOPIC })
      .catch(() => {
        // no-op if the room isn't ready
      });
  }

  return (
    <Scaffold
      persona={persona}
      stage={<VoiceStage persona={persona} />}
      transcript={<TranscriptPanel turns={turns} live className="h-full" />}
      timer={<SessionTimer running={connected} />}
      controls={
        <div className="flex flex-col items-center gap-3">
          {/* Visible only when the browser blocks autoplay — StartAudio toggles
              its own `display`, so a sighted user can click to enable audio. */}
          <StartAudio
            label={t(messages, "interview.enableAudio")}
            className="rounded-full border border-accent bg-accent-soft px-4 py-2 text-[13px] font-medium text-accent transition-colors hover:bg-accent hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-paper"
          />
          <ControlBar
            micEnabled={isMicrophoneEnabled}
            onToggleMute={() => void toggleMute()}
            onEnd={() => void endInterview()}
            ending={ending}
          />
        </div>
      }
      textFallback={<TextFallback onSend={sendText} />}
      notice={
        micError ? (
          <ErrorNotice
            title={t(messages, "interview.micUnavailable")}
            message={`${micError} ${t(messages, "interview.micTypeFallback")}`}
          />
        ) : agentNeverJoined ? (
          <ErrorNotice
            title={t(messages, "interview.agentMissing")}
            message={t(messages, "interview.agentMissingBody")}
          />
        ) : reconnecting ? (
          <div
            role="status"
            aria-live="polite"
            className="mx-auto mt-6 max-w-xl rounded-card border border-line bg-paper/70 px-4 py-3 text-center text-[13px] text-muted backdrop-blur-sm"
          >
            {t(messages, "interview.reconnecting")}
          </div>
        ) : null
      }
    />
  );
}

/* ------------------------------------------------------------------ */
/* PREVIEW session — zero LiveKit hooks; static sample data offline.    */
/* ------------------------------------------------------------------ */

function PreviewSession({
  persona,
  sessionId,
  reason,
}: {
  persona: Persona;
  sessionId: string;
  reason: "unconfigured" | "ended";
}) {
  const messages = useMessages();
  return (
    <Scaffold
      persona={persona}
      stage={<StagePreview persona={persona} />}
      transcript={<TranscriptPanel turns={SAMPLE_TURNS} className="h-full" />}
      timer={<SessionTimer running={false} />}
      controls={
        <ControlBar
          micEnabled
          onToggleMute={() => {}}
          onEnd={() => {}}
          disabled
        />
      }
      textFallback={<TextFallback onSend={() => {}} disabled />}
      notice={
        reason === "ended" ? (
          <ErrorNotice
            title={t(messages, "interview.endedTitle")}
            message={t(messages, "interview.endedBody")}
            action={
              <Link
                href={`/report/${encodeURIComponent(sessionId)}`}
                className="rounded-full border border-accent bg-accent-soft px-4 py-2 text-[13px] font-medium text-accent no-underline transition-colors hover:bg-accent hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-paper"
              >
                {t(messages, "interview.viewReport")}
              </Link>
            }
          />
        ) : (
          <div
            className={cn(
              "mx-auto mt-6 max-w-xl rounded-card border border-line",
              "bg-paper/70 px-4 py-3 text-center text-[13px] text-muted backdrop-blur-sm",
            )}
            role="status"
          >
            {t(messages, "interview.previewBody")}
          </div>
        )
      }
    />
  );
}

/* ------------------------------------------------------------------ */
/* Connecting shell — pre-mount of the genuine live path (no env notice).*/
/* ------------------------------------------------------------------ */

function ConnectingShell({ persona }: { persona: Persona }) {
  const messages = useMessages();
  return (
    <Scaffold
      persona={persona}
      stage={<StagePreview persona={persona} />}
      transcript={<TranscriptPanel turns={[]} className="h-full" />}
      timer={<SessionTimer running={false} />}
      controls={
        <ControlBar
          micEnabled
          onToggleMute={() => {}}
          onEnd={() => {}}
          disabled
        />
      }
      textFallback={<TextFallback onSend={() => {}} disabled />}
      notice={
        <div
          className="mx-auto mt-6 max-w-xl rounded-card border border-line bg-paper/70 px-4 py-3 text-center text-[13px] text-muted backdrop-blur-sm"
          role="status"
        >
          {t(messages, "interview.connectingShort")}
        </div>
      }
    />
  );
}

/* ------------------------------------------------------------------ */
/* Connection-lost shell — honest failure state with a rejoin action.   */
/* ------------------------------------------------------------------ */

function ConnectionLostShell({
  persona,
  message,
  onRejoin,
}: {
  persona: Persona;
  message: string;
  onRejoin: () => void;
}) {
  const messages = useMessages();
  return (
    <Scaffold
      persona={persona}
      stage={<StagePreview persona={persona} />}
      transcript={<TranscriptPanel turns={[]} className="h-full" />}
      timer={<SessionTimer running={false} />}
      controls={
        <ControlBar
          micEnabled
          onToggleMute={() => {}}
          onEnd={() => {}}
          disabled
        />
      }
      textFallback={<TextFallback onSend={() => {}} disabled />}
      notice={
        <ErrorNotice
          title={t(messages, "interview.connLost")}
          message={message}
          action={
            <button
              type="button"
              onClick={onRejoin}
              className="rounded-full border border-accent bg-accent-soft px-4 py-2 text-[13px] font-medium text-accent transition-colors hover:bg-accent hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-paper"
            >
              {t(messages, "interview.rejoin")}
            </button>
          }
        />
      }
    />
  );
}

/* ------------------------------------------------------------------ */
/* Orchestrator.                                                        */
/* ------------------------------------------------------------------ */

export function LiveRoom({
  sessionId,
  persona,
  token,
  url,
  previewReason = "unconfigured",
}: LiveRoomProps) {
  const router = useRouter();
  const messages = useMessages();

  // Guard the browser-only LiveKit client from SSR / first hydration.
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);

  // Failure UX state. `micError` keeps the room mounted (the candidate can
  // still hear the interviewer and type answers); `connectionLost` unmounts
  // the room and offers a rejoin. `joinAttempt` keys <LiveKitRoom> so each
  // rejoin is a clean reconnect.
  const [micError, setMicError] = React.useState<string | null>(null);
  const [connectionLost, setConnectionLost] = React.useState<string | null>(
    null,
  );
  const [joinAttempt, setJoinAttempt] = React.useState(0);

  const handleError = React.useCallback(
    (error: Error) => {
      // Device-capture failures surface here too (the room enables the mic via
      // the `audio` prop); classify them as mic problems, not connection loss.
      const failure = MediaDeviceFailure.getFailure(error);
      if (failure) {
        setMicError(describeMicFailure(messages, failure));
        return;
      }
      setConnectionLost(t(messages, "interview.couldntReach"));
    },
    [messages],
  );

  const handleMediaDeviceFailure = React.useCallback(
    (failure?: MediaDeviceFailure) => {
      setMicError(describeMicFailure(messages, failure));
    },
    [messages],
  );

  const handleDisconnected = React.useCallback(
    (reason?: DisconnectReason) => {
      // Intentional leave (End interview → navigation): not an error.
      if (reason === DisconnectReason.CLIENT_INITIATED) return;
      // The server closed the room — the interview is over; show the report.
      if (reason === DisconnectReason.ROOM_DELETED) {
        router.push(`/report/${encodeURIComponent(sessionId)}`);
        return;
      }
      setConnectionLost(t(messages, "interview.connDropped"));
    },
    [router, sessionId, messages],
  );

  function rejoin() {
    setMicError(null);
    setConnectionLost(null);
    setJoinAttempt((n) => n + 1);
  }

  const canConnect = Boolean(token && url);

  // Offline / not-connected: the build + no-keys path. Renders fully.
  if (!canConnect) {
    return (
      <PreviewSession
        persona={persona}
        sessionId={sessionId}
        reason={previewReason}
      />
    );
  }

  // Before mount (genuine live path), show a neutral connecting shell so SSR
  // markup matches and the browser-only LiveKit client spins up client-side —
  // without flashing the offline "set LIVEKIT_*" notice.
  if (!mounted) {
    return <ConnectingShell persona={persona} />;
  }

  // Honest failure state: never leave the candidate staring at an idle avatar.
  if (connectionLost) {
    return (
      <ConnectionLostShell
        persona={persona}
        message={connectionLost}
        onRejoin={rejoin}
      />
    );
  }

  return (
    <LiveKitRoom
      key={joinAttempt}
      serverUrl={url ?? undefined}
      token={token ?? undefined}
      connect
      audio
      video={false}
      data-session={sessionId}
      onError={handleError}
      onMediaDeviceFailure={handleMediaDeviceFailure}
      onDisconnected={handleDisconnected}
    >
      <RoomAudioRenderer />
      <LiveSession
        persona={persona}
        sessionId={sessionId}
        micError={micError}
        onMicError={setMicError}
      />
    </LiveKitRoom>
  );
}
