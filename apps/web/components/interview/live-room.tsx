"use client";

/**
 * <LiveRoom> — the WP-2 live interview screen orchestrator.
 *
 * Two strictly-separated paths share the SAME calm, centered layout:
 *
 *  • LIVE  (token && url): renders `<LiveKitRoom connect audio video={false}>`
 *    with `<RoomAudioRenderer/>` + `<StartAudio/>` and the hook-driven
 *    `<LiveSession/>`. Every LiveKit hook (useVoiceAssistant, useTranscriptions,
 *    useDataChannel, useLocalParticipant, useConnectionState) lives ONLY inside
 *    that provider — `<LiveSession/>` is never rendered outside it.
 *
 *  • PREVIEW (no token): renders the identical layout from static sample data
 *    via `<PreviewSession/>`, which calls ZERO LiveKit hooks. This is the
 *    offline path the build runs with no env keys — the page renders fully.
 *
 * The room subtree is additionally gated behind a mounted flag so the
 * browser-only LiveKit client never runs during SSR/hydration.
 */

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  StartAudio,
  useConnectionState,
  useDataChannel,
  useLocalParticipant,
  useTranscriptions,
} from "@livekit/components-react";
import { ConnectionState } from "livekit-client";
import "@livekit/components-styles";

import type { Persona } from "@/lib/personas";
import { cn } from "@/lib/cn";
import { VoiceStage, StagePreview } from "@/components/interview/voice-stage";
import {
  TranscriptPanel,
  type Turn,
} from "@/components/interview/transcript-panel";
import { ControlBar } from "@/components/interview/control-bar";
import { SessionTimer } from "@/components/interview/session-timer";
import { TextFallback } from "@/components/interview/text-fallback";

/** Topic for typed-answer fallback messages on the data channel. */
const TEXT_TOPIC = "candidate-text";

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

function LiveSession({
  persona,
  sessionId,
}: {
  persona: Persona;
  sessionId: string;
}) {
  const router = useRouter();
  const connectionState = useConnectionState();
  const connected = connectionState === ConnectionState.Connected;

  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant();
  const transcriptions = useTranscriptions();
  const { send } = useDataChannel(TEXT_TOPIC);

  const [ending, setEnding] = React.useState(false);

  // Map streaming transcriptions → turns. "You" when the segment belongs to the
  // local participant, otherwise the interviewer (agent / avatar worker).
  const turns: Turn[] = React.useMemo(() => {
    const localIdentity = localParticipant.identity;
    return transcriptions
      .filter((t) => t.text.trim().length > 0)
      .map((t) => ({
        id: t.streamInfo.id,
        role:
          t.participantInfo.identity === localIdentity
            ? ("candidate" as const)
            : ("interviewer" as const),
        text: t.text,
      }));
  }, [transcriptions, localParticipant.identity]);

  async function toggleMute() {
    await localParticipant.setMicrophoneEnabled(!isMicrophoneEnabled);
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
    try {
      void send(new TextEncoder().encode(text), { reliable: true });
    } catch {
      // no-op if the channel isn't ready
    }
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
            label="Enable interview audio"
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
    />
  );
}

/* ------------------------------------------------------------------ */
/* PREVIEW session — zero LiveKit hooks; static sample data offline.    */
/* ------------------------------------------------------------------ */

function PreviewSession({ persona }: { persona: Persona }) {
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
        <div
          className={cn(
            "mx-auto mt-6 max-w-xl rounded-card border border-line",
            "bg-paper/70 px-4 py-3 text-center text-[13px] text-muted backdrop-blur-sm",
          )}
          role="status"
        >
          Preview mode — connect LiveKit (set{" "}
          <code className="font-mono text-[12px] text-ink-soft">LIVEKIT_*</code>{" "}
          in <code className="font-mono text-[12px] text-ink-soft">.env</code>)
          to go live.
        </div>
      }
    />
  );
}

/* ------------------------------------------------------------------ */
/* Connecting shell — pre-mount of the genuine live path (no env notice).*/
/* ------------------------------------------------------------------ */

function ConnectingShell({ persona }: { persona: Persona }) {
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
          Connecting…
        </div>
      }
    />
  );
}

/* ------------------------------------------------------------------ */
/* Orchestrator.                                                        */
/* ------------------------------------------------------------------ */

export function LiveRoom({ sessionId, persona, token, url }: LiveRoomProps) {
  // Guard the browser-only LiveKit client from SSR / first hydration.
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);

  const canConnect = Boolean(token && url);

  // Offline / not-connected: the build + no-keys path. Renders fully.
  if (!canConnect) {
    return <PreviewSession persona={persona} />;
  }

  // Before mount (genuine live path), show a neutral connecting shell so SSR
  // markup matches and the browser-only LiveKit client spins up client-side —
  // without flashing the offline "set LIVEKIT_*" notice.
  if (!mounted) {
    return <ConnectingShell persona={persona} />;
  }

  return (
    <LiveKitRoom
      serverUrl={url ?? undefined}
      token={token ?? undefined}
      connect
      audio
      video={false}
      data-session={sessionId}
    >
      <RoomAudioRenderer />
      <LiveSession persona={persona} sessionId={sessionId} />
    </LiveKitRoom>
  );
}
