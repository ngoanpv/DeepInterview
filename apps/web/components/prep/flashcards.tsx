"use client";

import { useMemo, useState } from "react";
import { RotateCcw, Check } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Eyebrow } from "@/components/ui/eyebrow";
import { cn } from "@/lib/cn";
import {
  newCard,
  schedule,
  isDue,
  previewInterval,
  type Rating,
  type SrsState,
} from "@/lib/srs";
import { SAMPLE_FLASHCARDS, type Flashcard } from "@/lib/sample-mastery";

const RATINGS: { rating: Rating; label: string; variant: "out" | "ink" }[] = [
  { rating: "again", label: "Again", variant: "out" },
  { rating: "hard", label: "Hard", variant: "out" },
  { rating: "good", label: "Good", variant: "out" },
  { rating: "easy", label: "Easy", variant: "ink" },
];

/**
 * Spaced-repetition review. Cards flip (front → back) via a CSS 3D transform —
 * no `motion` dependency. Rating a card runs the inline FSRS-like (SM-2)
 * scheduler in `lib/srs.ts` and advances to the next still-due card.
 *
 * Scheduler state lives in `useState`, seeded inside the initializer so the
 * clock is read on the client only (SSR-safe, no hydration mismatch).
 */
export function Flashcards({
  cards = SAMPLE_FLASHCARDS,
}: {
  cards?: Flashcard[];
}) {
  // Seed per-card SRS state once, on the client, off a single `now`.
  const [states, setStates] = useState<Record<string, SrsState>>(() => {
    const now = Date.now();
    const seed: Record<string, SrsState> = {};
    for (const c of cards) seed[c.id] = newCard(now);
    return seed;
  });
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [reviewedThisSession, setReviewedThisSession] = useState(0);

  // Cards still due "right now" (computed off the same instant we render).
  const now = Date.now();
  const dueIds = useMemo(
    () =>
      cards
        .filter((c) => isDue(states[c.id] ?? newCard(now), now))
        .map((c) => c.id),
    [cards, states, now],
  );

  const current = cards[index];
  const allDone = dueIds.length === 0;

  function rate(rating: Rating) {
    if (!current) return;
    const at = Date.now();
    const prev = states[current.id] ?? newCard(at);
    setStates((s) => ({ ...s, [current.id]: schedule(prev, rating, at) }));
    setReviewedThisSession((n) => n + 1);
    setFlipped(false);

    // Advance to the next card that is still due after this rating.
    const order = cards.map((c) => c.id);
    const start = (index + 1) % cards.length;
    for (let step = 0; step < cards.length; step++) {
      const i = (start + step) % cards.length;
      const id = order[i];
      if (!id) continue;
      // The card we just rated is no longer due (we pushed it into the future).
      const st =
        id === current.id
          ? schedule(prev, rating, at)
          : (states[id] ?? newCard(at));
      if (isDue(st, at)) {
        setIndex(i);
        return;
      }
    }
    // None left due — park on the current index; the "all caught up" state shows.
    setIndex(index);
  }

  function resetSession() {
    const at = Date.now();
    const seed: Record<string, SrsState> = {};
    for (const c of cards) seed[c.id] = newCard(at);
    setStates(seed);
    setIndex(0);
    setFlipped(false);
    setReviewedThisSession(0);
  }

  const total = cards.length;
  const dueCount = dueIds.length;
  const progressPct =
    total > 0 ? Math.round(((total - dueCount) / total) * 100) : 0;

  return (
    <section aria-labelledby="flashcards-heading">
      <header className="mb-4 flex items-end justify-between">
        <div>
          <Eyebrow>Spaced repetition</Eyebrow>
          <h2
            id="flashcards-heading"
            className="mt-2 font-serif text-2xl text-ink"
          >
            Flashcards
          </h2>
        </div>
        <div className="text-right">
          <p className="font-mono text-[13px] text-ink-soft">{dueCount} due</p>
          <p className="font-mono text-[11px] text-faint">
            {reviewedThisSession} reviewed
          </p>
        </div>
      </header>

      {/* Progress bar */}
      <div
        className="mb-4 h-1.5 w-full overflow-hidden rounded-full bg-line"
        role="progressbar"
        aria-valuenow={progressPct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Review progress"
      >
        <div
          className="h-full rounded-full bg-accent transition-[width] duration-300"
          style={{ width: `${progressPct}%` }}
        />
      </div>

      {allDone || !current ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-[#e8f3ec]">
              <Check className="h-6 w-6 text-ok" aria-hidden />
            </span>
            <h3 className="font-serif text-xl text-ink">All caught up</h3>
            <p className="max-w-sm text-[14px] leading-relaxed text-muted">
              You&apos;ve cleared every card due right now. Come back when they
              resurface, or reset to drill the whole deck again.
            </p>
            <Button
              variant="out"
              size="sm"
              onClick={resetSession}
              className="mt-1"
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden />
              Reset deck
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Flip card. CSS 3D transform — no animation library. */}
          <div
            className="[perspective:1600px]"
            role="button"
            tabIndex={0}
            aria-label={flipped ? "Show question" : "Reveal answer"}
            onClick={() => setFlipped((f) => !f)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                setFlipped((f) => !f);
              }
            }}
          >
            <div
              className="relative min-h-[220px] w-full transition-transform duration-500 [transform-style:preserve-3d]"
              style={{
                transform: flipped ? "rotateY(180deg)" : "rotateY(0deg)",
              }}
            >
              {/* Front */}
              <div className="absolute inset-0 [backface-visibility:hidden]">
                <Card className="flex h-full min-h-[220px] flex-col">
                  <CardContent className="flex flex-1 flex-col items-center justify-center gap-3 py-8 text-center">
                    <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-faint">
                      {current.competency}
                    </span>
                    <p className="max-w-md font-serif text-[20px] leading-snug text-ink">
                      {current.front}
                    </p>
                    <span className="mt-2 text-[12px] text-faint">
                      Tap to reveal
                    </span>
                  </CardContent>
                </Card>
              </div>
              {/* Back */}
              <div
                className="absolute inset-0 [backface-visibility:hidden]"
                style={{ transform: "rotateY(180deg)" }}
              >
                <Card className="flex h-full min-h-[220px] flex-col bg-accent-soft">
                  <CardContent className="flex flex-1 flex-col items-center justify-center gap-3 py-8 text-center">
                    <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-accent">
                      Answer
                    </span>
                    <p className="max-w-lg text-[15px] leading-relaxed text-ink-soft">
                      {current.back}
                    </p>
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>

          {/* Rating row — only meaningful once the answer is shown. */}
          <div
            className={cn(
              "mt-4 grid grid-cols-4 gap-2 transition-opacity duration-200",
              flipped ? "opacity-100" : "pointer-events-none opacity-40",
            )}
          >
            {RATINGS.map(({ rating, label, variant }) => {
              const st = states[current.id] ?? newCard(now);
              return (
                <Button
                  key={rating}
                  variant={variant}
                  size="sm"
                  onClick={() => rate(rating)}
                  disabled={!flipped}
                  className="flex-col gap-0.5 py-2"
                >
                  <span>{label}</span>
                  <span className="font-mono text-[10px] opacity-70">
                    {previewInterval(st, rating, now)}
                  </span>
                </Button>
              );
            })}
          </div>
          <p className="mt-2 text-center font-mono text-[11px] text-faint">
            FSRS-like scheduler (SM-2): each rating sets the next review
            interval.
          </p>
        </>
      )}
    </section>
  );
}
