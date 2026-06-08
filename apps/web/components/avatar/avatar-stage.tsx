"use client";

/**
 * <AvatarStage> — the avatar centerpiece (WP-9).
 *
 * Two stacked, always-mounted <video loop muted playsInline> layers (idle +
 * speaking) crossfaded by opacity from the `state` prop. WP-2 wires this by
 * passing `useVoiceAssistant().state` straight through — this component stays
 * fully decoupled from LiveKit and is driven entirely by props.
 *
 * Graceful, asset-free fallback (load-bearing): no real loops exist yet, so the
 * placeholder URLs all 404. Rather than flash a broken <video>, the fallback
 * "stage" renders by DEFAULT and a video layer reveals itself only once its
 * `onLoadedData` fires (and hides again on `onError`). With zero assets the
 * fallback is what you see — a calm, editorial gradient panel with the persona
 * name and a state-aware breathing pulse — so the component looks intentional
 * offline. When real MP4s land in `lib/personas.ts`, the videos take over with
 * no code change.
 */

import * as React from "react";
import { cn } from "@/lib/cn";
import type { Persona } from "@/lib/personas";

export type AvatarState = "idle" | "listening" | "thinking" | "speaking";

export interface AvatarStageProps {
  persona: Persona;
  state: AvatarState;
  className?: string;
}

/**
 * Per-persona fallback hues — kept inside the editorial palette (light, paper,
 * one indigo accent). Each is a subtle two-stop gradient + a soft accent glow,
 * so the three personas read as distinct without leaving the design language.
 */
const FALLBACK_STYLE: Record<
  Persona["id"],
  { gradient: string; glow: string; accent: string }
> = {
  // Anime — warm pastel rose/peach, soft and friendly.
  anime: {
    gradient: "linear-gradient(165deg, #fdf6f3 0%, #f7eef0 55%, #f0ecf6 100%)",
    glow: "radial-gradient(120% 90% at 50% 18%, rgba(225,150,170,0.22), transparent 60%)",
    accent: "#b65a78",
  },
  // Superhero — cool steel/indigo, calm and heroic.
  superhero: {
    gradient: "linear-gradient(165deg, #f3f5fb 0%, #eceef8 55%, #e8eaf4 100%)",
    glow: "radial-gradient(120% 90% at 50% 18%, rgba(67,56,202,0.20), transparent 60%)",
    accent: "#4338ca",
  },
  // Recruiter — neutral office grey-green, professional and warm.
  recruiter: {
    gradient: "linear-gradient(165deg, #faf9f6 0%, #f2f1ec 55%, #edefee 100%)",
    glow: "radial-gradient(120% 90% at 50% 18%, rgba(120,140,130,0.20), transparent 60%)",
    accent: "#4a6b5d",
  },
};

type LayerStatus = "loading" | "ready" | "error";

const STATE_LABEL: Record<AvatarState, string> = {
  idle: "IDLE",
  listening: "LISTENING",
  thinking: "THINKING",
  speaking: "SPEAKING",
};

/**
 * Scoped keyframes for the fallback breathing/pulse. Injected as a plain <style>
 * (not styled-jsx) so it needs no globals.css edit and no extra dep. Both
 * animations freeze under `prefers-reduced-motion` per the a11y requirement.
 */
const STAGE_KEYFRAMES = `
@keyframes di-avatar-breathe {
  0%, 100% { opacity: 0.55; transform: scale(1); }
  50%      { opacity: 0.8;  transform: scale(1.03); }
}
@keyframes di-avatar-speak {
  0%, 100% { opacity: 0.6;  transform: scale(1); }
  50%      { opacity: 1;    transform: scale(1.08); }
}
.di-avatar-pulse { animation: di-avatar-breathe 4.5s ease-in-out infinite; }
.di-avatar-pulse[data-speaking="true"] { animation: di-avatar-speak 1.6s ease-in-out infinite; }
@media (prefers-reduced-motion: reduce) {
  .di-avatar-pulse { animation: none !important; }
}
`;

export function AvatarStage({ persona, state, className }: AvatarStageProps) {
  const [idleStatus, setIdleStatus] = React.useState<LayerStatus>("loading");
  const [speakStatus, setSpeakStatus] = React.useState<LayerStatus>("loading");

  const speaking = state === "speaking";
  // Everything that isn't `speaking` (idle / listening / thinking) shows idle.
  const showSpeakingLayer = speaking;

  const idleReady = idleStatus === "ready";
  const speakReady = speakStatus === "ready";
  // Fallback owns the stage whenever the layer we'd want to show isn't ready.
  const fallbackVisible = showSpeakingLayer ? !speakReady : !idleReady;

  const look = FALLBACK_STYLE[persona.id];

  return (
    <div
      className={cn(
        "relative aspect-[4/5] w-full overflow-hidden rounded-card",
        "border border-line bg-panel select-none",
        className,
      )}
      role="img"
      aria-label={`${persona.name} avatar, ${STATE_LABEL[state].toLowerCase()}`}
    >
      <style>{STAGE_KEYFRAMES}</style>

      {/* Fallback stage — rendered by default; video layers cover it once ready. */}
      <div
        aria-hidden="true"
        className={cn(
          "absolute inset-0 transition-opacity duration-300 ease-out",
          fallbackVisible ? "opacity-100" : "opacity-0",
        )}
        style={{ background: look.gradient }}
      >
        {/* Soft accent glow + breathing orb behind the name. */}
        <div className="absolute inset-0" style={{ background: look.glow }} />
        <div
          className="di-avatar-pulse absolute left-1/2 top-[34%] h-40 w-40 -translate-x-1/2 -translate-y-1/2 rounded-full blur-2xl"
          data-speaking={speaking}
          style={{ backgroundColor: look.accent, opacity: 0.5 }}
        />

        {/* Persona identity. */}
        <div className="absolute inset-x-0 bottom-0 flex flex-col items-center gap-1 px-5 pb-7 text-center">
          <span className="serif text-2xl text-ink">{persona.name}</span>
          <span className="max-w-[26ch] text-xs leading-snug text-muted">
            {persona.style}
          </span>
        </div>
      </div>

      {/* Idle layer — visible for idle/listening/thinking. */}
      <video
        className={cn(
          "absolute inset-0 h-full w-full object-cover",
          "transition-opacity duration-300 ease-out",
          !showSpeakingLayer && idleReady ? "opacity-100" : "opacity-0",
        )}
        src={persona.idle_url}
        poster={persona.poster_url}
        loop
        muted
        playsInline
        preload="auto"
        autoPlay
        onLoadedData={() => setIdleStatus("ready")}
        onError={() => setIdleStatus("error")}
      />

      {/* Speaking layer — visible only for `speaking`. */}
      <video
        className={cn(
          "absolute inset-0 h-full w-full object-cover",
          "transition-opacity duration-300 ease-out",
          showSpeakingLayer && speakReady ? "opacity-100" : "opacity-0",
        )}
        src={persona.speaking_url}
        loop
        muted
        playsInline
        preload="auto"
        autoPlay
        onLoadedData={() => setSpeakStatus("ready")}
        onError={() => setSpeakStatus("error")}
      />

      {/* State pill — small, mono, for at-a-glance clarity. */}
      <div className="absolute left-3 top-3 z-10">
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md px-2 py-0.5",
            "bg-paper/85 font-mono text-[10px] tracking-[0.12em] text-ink-soft",
            "border border-line backdrop-blur-sm",
          )}
        >
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              speaking ? "bg-accent" : "bg-faint",
            )}
          />
          {STATE_LABEL[state]}
        </span>
      </div>
    </div>
  );
}
