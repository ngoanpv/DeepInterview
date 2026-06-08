"use client";

/**
 * <ControlBar> — the small, subtle live-interview controls (WP-2).
 *
 * Pure presentational: mute toggle + end-interview, driven entirely by props so
 * the LIVE container can wire real room controls and the PREVIEW container can
 * render the same chrome disabled. Restrained styling — a calm frosted bar.
 */

import { Mic, MicOff, PhoneOff } from "lucide-react";
import { cn } from "@/lib/cn";

export interface ControlBarProps {
  /** True when the mic is publishing; false when muted. */
  micEnabled: boolean;
  onToggleMute: () => void;
  onEnd: () => void;
  /** Disable all controls (preview / not connected). */
  disabled?: boolean;
  /** True while the end action is in flight. */
  ending?: boolean;
  className?: string;
}

export function ControlBar({
  micEnabled,
  onToggleMute,
  onEnd,
  disabled = false,
  ending = false,
  className,
}: ControlBarProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded-full border border-line",
        "bg-paper/80 p-1.5 backdrop-blur-md",
        className,
      )}
      role="group"
      aria-label="Interview controls"
    >
      <button
        type="button"
        onClick={onToggleMute}
        disabled={disabled}
        aria-pressed={!micEnabled}
        aria-label={micEnabled ? "Mute microphone" : "Unmute microphone"}
        className={cn(
          "inline-flex h-10 w-10 items-center justify-center rounded-full",
          "transition-colors duration-150",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-paper",
          "disabled:opacity-40 disabled:pointer-events-none",
          micEnabled
            ? "text-ink-soft hover:bg-accent-soft hover:text-ink"
            : "bg-accent-soft text-accent",
        )}
      >
        {micEnabled ? (
          <Mic className="h-[18px] w-[18px]" aria-hidden />
        ) : (
          <MicOff className="h-[18px] w-[18px]" aria-hidden />
        )}
      </button>

      <button
        type="button"
        onClick={onEnd}
        disabled={disabled || ending}
        aria-label="End interview"
        className={cn(
          "inline-flex h-10 items-center gap-2 rounded-full px-4",
          "bg-ink text-[13px] font-medium text-white",
          "transition-colors duration-150 hover:bg-ink-soft",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-paper",
          "disabled:opacity-40 disabled:pointer-events-none",
        )}
      >
        <PhoneOff className="h-4 w-4" aria-hidden />
        {ending ? "Ending…" : "End"}
      </button>
    </div>
  );
}
