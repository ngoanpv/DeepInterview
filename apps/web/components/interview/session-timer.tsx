"use client";

/**
 * <SessionTimer> — a calm mm:ss elapsed clock for the live interview (WP-2).
 *
 * Pure presentational: it owns only a tick interval and is driven by `running`.
 * The container starts it on *connect* (not on mount) by flipping `running`, so
 * it never ticks during the connecting/buffering phase. In preview (offline)
 * mode it renders a static `00:00`.
 *
 * Calm, restrained styling: mono, faint, hairline frosted chip — an interview is
 * already high-stress, so the clock is glanceable but never loud.
 */

import * as React from "react";
import { cn } from "@/lib/cn";

export interface SessionTimerProps {
  /** When true the clock ticks; flip on connect. Static 00:00 when false. */
  running: boolean;
  className?: string;
}

function format(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function SessionTimer({ running, className }: SessionTimerProps) {
  const [seconds, setSeconds] = React.useState(0);
  // Remember when the clock first started so a pause/resume keeps the total.
  const startedAtRef = React.useRef<number | null>(null);
  const baseRef = React.useRef(0);

  React.useEffect(() => {
    if (!running) {
      // Freeze the accumulated total; clear the start marker.
      baseRef.current = seconds;
      startedAtRef.current = null;
      return;
    }
    startedAtRef.current = Date.now();
    const id = window.setInterval(() => {
      const started = startedAtRef.current;
      if (started == null) return;
      const elapsed = Math.floor((Date.now() - started) / 1000);
      setSeconds(baseRef.current + elapsed);
    }, 500);
    return () => window.clearInterval(id);
    // `seconds` is intentionally omitted: we snapshot it into baseRef on stop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running]);

  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded-full border border-line",
        "bg-paper/70 px-3 py-1 backdrop-blur-sm",
        className,
      )}
      role="timer"
      aria-label="Interview elapsed time"
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          running ? "bg-accent" : "bg-faint",
        )}
        aria-hidden
      />
      <span className="font-mono text-[12px] tabular-nums tracking-[0.08em] text-muted">
        {format(seconds)}
      </span>
    </div>
  );
}
