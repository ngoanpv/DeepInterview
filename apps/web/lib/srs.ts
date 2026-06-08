/**
 * Minimal spaced-repetition scheduler — "FSRS-like (SM-2 scheduler)".
 *
 * NOTE ON HONESTY: real FSRS uses a 17-parameter weight vector and a
 * stability/difficulty memory model. That is overkill (and bug-prone) to inline,
 * so this is a deliberately small **SM-2-style** scheduler. It speaks the exact
 * `ease` / `interval` / `due` vocabulary the Prep Coach needs, schedules the next
 * review from a four-button rating, and is a pure function so it is trivial to
 * test and free of side effects (no `Date.now()` at module scope — the caller
 * passes `now`, keeping it SSR/hydration-safe).
 */

/** The four review grades, hardest → easiest. */
export type Rating = "again" | "hard" | "good" | "easy";

/** Per-card scheduling state. `due` is an epoch-ms timestamp. */
export interface SrsState {
  /** Ease factor (a.k.a. EF). Clamped to a floor of 1.3, like SM-2. */
  ease: number;
  /** Inter-review interval, in days. */
  interval: number;
  /** Next-review timestamp (epoch ms). */
  due: number;
  /** Total times this card has been reviewed (for progress UI). */
  reps: number;
}

const MS_PER_DAY = 24 * 60 * 60 * 1000;
const MIN_EASE = 1.3;
const DEFAULT_EASE = 2.5;

/** A fresh, never-reviewed card, due immediately at `now`. */
export function newCard(now: number): SrsState {
  return { ease: DEFAULT_EASE, interval: 0, due: now, reps: 0 };
}

function clampEase(ease: number): number {
  return Math.max(MIN_EASE, Math.round(ease * 100) / 100);
}

/**
 * Schedule the next review. Pure: returns a NEW state, never mutates input.
 *
 *   again → lapse: interval back to ~1 day, ease −0.20
 *   hard  → interval × 1.2,             ease −0.15
 *   good  → interval × ease,            ease unchanged
 *   easy  → interval × ease × 1.3,      ease +0.15
 *
 * Ease is floored at 1.3. The first successful review starts the interval at 1
 * day (a card with interval 0 can't multiply its way off the floor).
 */
export function schedule(
  state: SrsState,
  rating: Rating,
  now: number,
): SrsState {
  let { ease, interval } = state;
  const base = interval > 0 ? interval : 1;

  switch (rating) {
    case "again":
      ease = clampEase(ease - 0.2);
      interval = 1;
      break;
    case "hard":
      ease = clampEase(ease - 0.15);
      interval = Math.max(1, Math.round(base * 1.2));
      break;
    case "good":
      // ease unchanged
      interval = Math.max(1, Math.round(base * ease));
      break;
    case "easy":
      ease = clampEase(ease + 0.15);
      interval = Math.max(1, Math.round(base * ease * 1.3));
      break;
  }

  return {
    ease,
    interval,
    due: now + interval * MS_PER_DAY,
    reps: state.reps + 1,
  };
}

/** A card is due when its `due` timestamp is at or before `now`. */
export function isDue(state: SrsState, now: number): boolean {
  return state.due <= now;
}

/** Human-friendly "next review" hint for a prospective rating, e.g. "3d". */
export function previewInterval(
  state: SrsState,
  rating: Rating,
  now: number,
): string {
  const next = schedule(state, rating, now);
  if (next.interval <= 0) return "now";
  if (next.interval === 1) return "1d";
  return `${next.interval}d`;
}
