"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BookOpen, FileText, History, Mic, RotateCcw } from "lucide-react";
import {
  getRecentSessions,
  rememberSession,
  type RecentSession,
} from "@/lib/recent-sessions";

type ServerSession = {
  session_id: string;
  company?: string | null;
  role?: string | null;
  created_at?: number | null;
  updated_at?: number | null;
};

/** Invisible: records this session id in local history on mount. */
export function RememberSession({ id, label }: { id: string; label?: string }) {
  useEffect(() => {
    rememberSession(id, label);
  }, [id, label]);
  return null;
}

/**
 * Links back to past interviews on this device: report, Prep Coach, and the
 * Socratic voice coach for each.
 */
export function RecentSessions({
  tone = "light",
  title = "Your recent interviews",
}: {
  tone?: "light" | "dark";
  title?: string;
}) {
  const [items, setItems] = useState<RecentSession[] | null>(null);
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    const local = getRecentSessions();
    setItems(local);
    // Merge in the agent's persisted list (SQLite store) when available.
    fetch("/api/sessions", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : { sessions: [] }))
      .then((body: { sessions?: ServerSession[] }) => {
        const merged = new Map(local.map((s) => [s.id, s]));
        for (const s of body.sessions ?? []) {
          const label =
            [s.role, s.company].filter(Boolean).join(" · ") || undefined;
          const at = (s.updated_at ?? s.created_at ?? 0) * 1000;
          const prev = merged.get(s.session_id);
          merged.set(s.session_id, {
            id: s.session_id,
            label: label ?? prev?.label,
            at: Math.max(at, prev?.at ?? 0),
          });
        }
        setItems([...merged.values()].sort((a, b) => b.at - a.at));
      })
      .catch(() => {});
  }, []);
  if (!items || items.length === 0) return null;

  const dark = tone === "dark";
  const visible = expanded ? items.slice(0, 10) : items.slice(0, 3);
  const hasMore = items.length > 3;

  const shell = dark
    ? "mt-2 rounded-xl border border-white/15 bg-white/5 px-4 py-3.5"
    : "mt-6 rounded-card border border-line bg-panel px-5 py-4";
  const divider = dark ? "divide-white/10" : "divide-line-2";
  const muted = dark ? "text-white/60" : "text-muted";
  const pill = dark
    ? "inline-flex items-center gap-1.5 rounded-full border border-white/20 px-2.5 py-1 text-[12px] font-medium text-white/90 no-underline transition hover:border-white/40 hover:bg-white/10"
    : "inline-flex items-center gap-1.5 rounded-full border border-line bg-paper px-2.5 py-1 text-[12px] font-medium text-ink-soft no-underline transition hover:border-ink-soft/40 hover:text-ink";
  const socraticPill = dark
    ? "inline-flex items-center gap-1.5 rounded-full border border-white/30 bg-white/15 px-2.5 py-1 text-[12px] font-medium text-white no-underline transition hover:bg-white/25"
    : "inline-flex items-center gap-1.5 rounded-full border border-accent/25 bg-accent-soft px-2.5 py-1 text-[12px] font-medium text-accent no-underline transition hover:border-accent/50";

  return (
    <section className={shell} aria-label={title}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <History className={`h-3.5 w-3.5 ${muted}`} aria-hidden />
          <p
            className={`font-mono text-[11px] uppercase tracking-[0.14em] ${muted}`}
          >
            {title}
          </p>
          <span
            className={`rounded-full px-2 py-0.5 font-mono text-[10.5px] ${
              dark ? "bg-white/10 text-white/70" : "bg-paper text-muted"
            }`}
          >
            {items.length}
          </span>
        </div>
        {hasMore && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className={`cursor-pointer text-[12px] underline-offset-2 hover:underline ${
              dark
                ? "text-white/70 hover:text-white"
                : "text-muted hover:text-ink"
            }`}
          >
            {expanded
              ? "Show less"
              : `Show all (${Math.min(items.length, 10)})`}
          </button>
        )}
      </div>

      <ul className={`mt-2.5 divide-y ${divider}`}>
        {visible.map((s) => {
          const id = encodeURIComponent(s.id);
          return (
            <li
              key={s.id}
              className="flex flex-col gap-2 py-2.5 first:pt-1 last:pb-0.5 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0">
                <p
                  className={`truncate text-[14px] font-medium ${
                    dark ? "text-white" : "text-ink"
                  }`}
                >
                  {s.label || `Interview ${s.id.slice(0, 8)}`}
                </p>
                <p className={`text-[12px] ${muted}`}>
                  {new Date(s.at).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-1.5 sm:shrink-0">
                <Link href={`/setup?from=${id}`} className={pill}>
                  <RotateCcw className="h-3 w-3" aria-hidden />
                  Redo mock
                </Link>
                <Link href={`/report/${id}`} className={pill}>
                  <FileText className="h-3 w-3" aria-hidden />
                  Report
                </Link>
                <Link href={`/prep?session=${id}`} className={pill}>
                  <BookOpen className="h-3 w-3" aria-hidden />
                  Prep Coach
                </Link>
                <Link
                  href={`/interview/coach?mode=socratic&session=${id}`}
                  className={socraticPill}
                >
                  <Mic className="h-3 w-3" aria-hidden />
                  Socratic
                </Link>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
