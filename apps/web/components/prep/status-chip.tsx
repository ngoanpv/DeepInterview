import { cn } from "@/lib/cn";
import type { MasteryState } from "@/lib/sample-mastery";

/**
 * Shared visual language for a competency's mastery state, used by the study
 * plan chips and (via the same palette) the mastery-graph nodes:
 *   unseen   → faint / neutral
 *   learning → accent-soft (indigo, the one accent)
 *   shaky    → amber (the single warm tone in the palette; inline hex since
 *              there is no `amber` token — kept tasteful and low-chroma)
 *   mastered → ok green
 */
export const MASTERY_LABEL: Record<MasteryState, string> = {
  unseen: "Not started",
  learning: "Learning",
  shaky: "Shaky",
  mastered: "Mastered",
};

/** Token/hex pairs for the four states, so node + chip stay in sync. */
export const MASTERY_COLORS: Record<
  MasteryState,
  { bg: string; fg: string; border: string }
> = {
  unseen: { bg: "#f4f3ef", fg: "#73737b", border: "#e7e3da" },
  learning: { bg: "#eef0fb", fg: "#4338ca", border: "#d7d9f4" },
  shaky: { bg: "#fbf2e6", fg: "#9a6212", border: "#efddc2" },
  mastered: { bg: "#e8f3ec", fg: "#15803d", border: "#cfe6d6" },
};

export function StatusChip({
  state,
  className,
}: {
  state: MasteryState;
  className?: string;
}) {
  const c = MASTERY_COLORS[state];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5",
        "text-[11px] font-mono font-medium",
        className,
      )}
      style={{ backgroundColor: c.bg, color: c.fg, borderColor: c.border }}
    >
      <span
        className="h-1.5 w-1.5 rounded-full"
        style={{ backgroundColor: c.fg }}
        aria-hidden
      />
      {MASTERY_LABEL[state]}
    </span>
  );
}
