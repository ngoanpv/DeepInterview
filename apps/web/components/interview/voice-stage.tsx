"use client";

/**
 * <VoiceStage> — the avatar centerpiece wired to the live voice loop (WP-2).
 *
 * LIVE path only: it calls `useVoiceAssistant()` (which reads room context) and
 * therefore must render *inside* `<LiveKitRoom>`. It maps the agent's
 * `AgentState` → the 4-state `AvatarState` that `<AvatarStage>` understands, and
 * overlays a `BarVisualizer` tied to the agent audio track, themed to the indigo
 * accent — the audio-reactive "listening → thinking → speaking" motif.
 *
 * The PREVIEW (offline) path never calls the hook; it renders `<StagePreview>`,
 * which shows the same frame with a static `idle` state and no visualizer.
 */

import { useVoiceAssistant, BarVisualizer } from "@livekit/components-react";
import type { AgentState } from "@livekit/components-react";
import { AvatarStage } from "@/components/avatar/avatar-stage";
import type { AvatarState } from "@/components/avatar/avatar-stage";
import type { Persona } from "@/lib/personas";
import { cn } from "@/lib/cn";

/**
 * Total, exhaustive map from the agent's full `AgentState` union to the 4-state
 * `AvatarState`. Only listening/thinking/speaking pass through; every other
 * phase (disconnected, connecting, pre-connect-buffering, failed, initializing,
 * idle) resolves to `idle` so no invalid state can reach `<AvatarStage>`.
 */
export function agentStateToAvatarState(state: AgentState): AvatarState {
  switch (state) {
    case "listening":
    case "thinking":
    case "speaking":
      return state;
    default:
      return "idle";
  }
}

/** Indigo-accent bar visualizer overlaid at the base of the stage. */
function AccentVisualizer({
  state,
  track,
}: {
  state: AgentState;
  track: React.ComponentProps<typeof BarVisualizer>["track"];
}) {
  return (
    <div
      className="pointer-events-none absolute inset-x-0 bottom-0 z-10 flex h-20 items-end justify-center gap-1 px-6 pb-5"
      aria-hidden
    >
      <BarVisualizer
        state={state}
        track={track}
        barCount={7}
        options={{ minHeight: 8, maxHeight: 80 }}
        className="flex h-full w-32 items-end justify-center gap-[3px] [&>span]:w-1.5 [&>span]:rounded-full [&>span]:bg-faint [&>span[data-lk-highlighted=true]]:bg-accent"
      />
    </div>
  );
}

export interface VoiceStageProps {
  persona: Persona;
  className?: string;
}

/** LIVE stage — must be a descendant of `<LiveKitRoom>`. */
export function VoiceStage({ persona, className }: VoiceStageProps) {
  const { state, audioTrack } = useVoiceAssistant();
  const avatarState = agentStateToAvatarState(state);

  return (
    <div className={cn("relative", className)}>
      <AvatarStage persona={persona} state={avatarState} />
      {audioTrack && <AccentVisualizer state={state} track={audioTrack} />}
    </div>
  );
}

/** PREVIEW stage — no LiveKit hooks; static idle for the offline screen. */
export function StagePreview({ persona, className }: VoiceStageProps) {
  return (
    <div className={cn("relative", className)}>
      <AvatarStage persona={persona} state="idle" />
    </div>
  );
}
