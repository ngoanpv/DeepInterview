"use client";

/**
 * <TranscriptPanel> — the live-caption panel (WP-2).
 *
 * Pure presentational + an autoscroll effect. It takes an ordered list of turns
 * and renders them as a frosted, scrollable transcript. Voice-UI convention:
 * captions stay visible for the whole call (accessibility + barge-in clarity),
 * so this panel is always mounted next to the avatar.
 *
 * Data source is decoupled: the LIVE container maps `useTranscriptions()` into
 * `Turn[]`; the PREVIEW container passes a short static sample so the screen
 * looks real fully offline. The whole region is an `aria-live="polite"` log so
 * a screen reader announces new turns as they stream in.
 */

import * as React from "react";
import { cn } from "@/lib/cn";

export type TurnRole = "interviewer" | "candidate";

export interface Turn {
  /** Stable id — use the transcription stream id when live. */
  id: string;
  role: TurnRole;
  text: string;
}

export interface TranscriptPanelProps {
  turns: Turn[];
  /** When true, render a subtle "listening…" affordance under the last turn. */
  live?: boolean;
  className?: string;
}

const ROLE_LABEL: Record<TurnRole, string> = {
  interviewer: "Interviewer",
  candidate: "You",
};

export function TranscriptPanel({
  turns,
  live = false,
  className,
}: TranscriptPanelProps) {
  const scrollRef = React.useRef<HTMLDivElement>(null);

  // Pin to the latest turn as the transcript grows.
  React.useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [turns]);

  return (
    <div
      className={cn(
        "flex flex-col overflow-hidden rounded-card border border-line",
        "bg-paper/70 backdrop-blur-md",
        className,
      )}
    >
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <span className="font-mono text-[10px] tracking-[0.14em] text-faint">
          TRANSCRIPT
        </span>
        {live && (
          <span className="flex items-center gap-1.5 font-mono text-[10px] tracking-[0.12em] text-muted">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
            LIVE
          </span>
        )}
      </div>

      <div
        ref={scrollRef}
        className="flex-1 space-y-3.5 overflow-y-auto px-4 py-4"
        aria-live="polite"
        aria-label="Interview transcript"
        role="log"
      >
        {turns.length === 0 ? (
          <p className="text-[13px] leading-relaxed text-faint">
            The conversation will appear here as you speak.
          </p>
        ) : (
          turns.map((turn) => (
            <div key={turn.id} className="flex flex-col gap-1">
              <span
                className={cn(
                  "font-mono text-[10px] tracking-[0.1em]",
                  turn.role === "candidate" ? "text-accent" : "text-faint",
                )}
              >
                {ROLE_LABEL[turn.role].toUpperCase()}
              </span>
              <p
                className={cn(
                  "text-[14px] leading-relaxed",
                  turn.role === "candidate" ? "text-ink" : "text-ink-soft",
                )}
              >
                {turn.text}
              </p>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
