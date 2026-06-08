import type { ScoreCard } from "@deepinterview/shared";
import { cn } from "@/lib/cn";
import { Eyebrow } from "@/components/ui/eyebrow";

/** Find a competency score by a case-insensitive substring match. */
function pick(scores: ScoreCard["competency_scores"], needle: string) {
  const n = needle.toLowerCase();
  return scores.find((c) => c.competency.toLowerCase().includes(n));
}

function verdict(score: number): string {
  if (score >= 4.25) return "Interview-ready";
  if (score >= 3.25) return "On track";
  if (score >= 2) return "Needs work";
  return "Early";
}

type Metric = {
  label: string;
  value: string;
  sub: string;
  /** 0-5 fill for the hairline meter; null hides the meter. */
  fill: number | null;
};

/**
 * Bento grid: a tall serif "overall /5" hero on the left, a 2x2 of derived
 * top-metric cards on the right (Communication, Technical depth, STAR, Filler
 * words). Server component — pure render off the parsed ScoreCard.
 */
export function ScoreBento({ scorecard }: { scorecard: ScoreCard }) {
  const cs = scorecard.competency_scores;
  const lr = scorecard.language_report;

  const comm = pick(cs, "commun");
  const tech = pick(cs, "techn") ?? pick(cs, "system");
  const star = pick(cs, "star") ?? pick(cs, "behav");

  const metrics: Metric[] = [
    {
      label: "Communication",
      value: comm ? comm.score.toFixed(1) : "—",
      sub: comm ? `${comm.level} · /5` : "no signal",
      fill: comm ? comm.score : null,
    },
    {
      label: "Technical Depth",
      value: tech ? tech.score.toFixed(1) : "—",
      sub: tech ? `${tech.level} · /5` : "no signal",
      fill: tech ? tech.score : null,
    },
    {
      label: "STAR Structure",
      value: star ? star.score.toFixed(1) : "—",
      sub: star ? `${star.level} · /5` : "no signal",
      fill: star ? star.score : null,
    },
    {
      label: "Filler Words",
      value: String(lr.filler_word_count),
      sub: "total · aim < 10",
      fill: null,
    },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-3">
      {/* Hero */}
      <div className="md:row-span-1 flex flex-col justify-between rounded-card border border-line bg-panel p-6 shadow-[0_1px_0_rgba(0,0,0,0.02),0_24px_48px_-28px_rgba(20,20,30,0.12)]">
        <Eyebrow>Overall</Eyebrow>
        <div className="mt-4 flex items-baseline gap-1">
          <span className="font-serif text-[64px] leading-none text-ink">
            {scorecard.overall_score.toFixed(1)}
          </span>
          <span className="font-serif text-2xl text-faint">/5</span>
        </div>
        <p className="mt-3 text-sm text-muted">
          {verdict(scorecard.overall_score)}
        </p>
      </div>

      {/* 2x2 metric tiles */}
      <div className="grid grid-cols-2 gap-4 md:col-span-2">
        {metrics.map((m) => (
          <div
            key={m.label}
            className="flex flex-col rounded-card border border-line bg-panel p-5 shadow-[0_1px_0_rgba(0,0,0,0.02),0_24px_48px_-28px_rgba(20,20,30,0.12)]"
          >
            <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-faint">
              {m.label}
            </p>
            <p className="mt-2 font-serif text-3xl text-ink">{m.value}</p>
            <p className="mt-0.5 text-xs capitalize text-muted">{m.sub}</p>
            {m.fill !== null && (
              <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-line">
                <div
                  className={cn(
                    "h-full rounded-full",
                    m.fill >= 3.25 ? "bg-accent" : "bg-faint",
                  )}
                  style={{ width: `${Math.min(100, (m.fill / 5) * 100)}%` }}
                />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
