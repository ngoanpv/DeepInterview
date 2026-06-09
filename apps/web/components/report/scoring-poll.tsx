"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Re-runs the server component (which re-fetches the session view) on an
 * interval while post-interview scoring is still in flight, so the report
 * flips to the real result the moment it's ready — without the user refreshing.
 * Renders nothing; unmounts (and stops polling) once `load()` returns a terminal
 * state and the page no longer renders this.
 */
export function ScoringPoll({ intervalMs = 2500 }: { intervalMs?: number }) {
  const router = useRouter();
  useEffect(() => {
    const t = setInterval(() => router.refresh(), intervalMs);
    return () => clearInterval(t);
  }, [router, intervalMs]);
  return null;
}
