import Link from "next/link";
import { Clock, ArrowRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Eyebrow } from "@/components/ui/eyebrow";
import { StatusChip } from "@/components/prep/status-chip";
import { SAMPLE_STUDY_PLAN, type StudyModule } from "@/lib/sample-mastery";

/**
 * The gap → path view: an ordered list of study modules built from the last
 * interview's weak competencies. Server component (no interactivity) — each
 * module is a card with its competency, mastery chip, "why it's here", and two
 * CTAs ("Start" to study, "Practice in a mock" to loop back into an interview).
 */
export function StudyPlan({
  modules = SAMPLE_STUDY_PLAN,
  weakAreas,
}: {
  modules?: StudyModule[];
  /** Weak competencies from the last interview, for the header tie-in. */
  weakAreas?: string[];
}) {
  const totalMin = modules.reduce((sum, m) => sum + m.est_min, 0);
  const gaps = weakAreas?.length ? weakAreas : ["your weak areas"];

  return (
    <section aria-labelledby="study-plan-heading">
      <header className="mb-4">
        <Eyebrow>Gap → study path</Eyebrow>
        <h2
          id="study-plan-heading"
          className="mt-2 font-serif text-2xl text-ink"
        >
          Your study plan
        </h2>
        <p className="mt-1 text-[14px] leading-relaxed text-muted">
          Built from your last interview&apos;s weak areas
          {weakAreas?.length ? (
            <>
              {" — "}
              <span className="text-ink-soft">{gaps.join(", ")}</span>
            </>
          ) : null}
          . {modules.length} modules · about {totalMin} min.
        </p>
      </header>

      <ol className="space-y-3">
        {modules.map((m, i) => (
          <li key={m.id}>
            <Card>
              <CardContent className="flex flex-col gap-4 py-5 sm:flex-row sm:items-center">
                <span
                  className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-soft font-mono text-[12px] text-accent"
                  aria-hidden
                >
                  {i + 1}
                </span>

                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-serif text-[17px] text-ink">
                      {m.title}
                    </h3>
                    <StatusChip state={m.status} />
                  </div>
                  <p className="mt-1 text-[13.5px] leading-relaxed text-muted">
                    {m.rationale}
                  </p>
                  <div className="mt-2 flex items-center gap-3 text-[12px] font-mono text-faint">
                    <span>{m.competency}</span>
                    <span className="inline-flex items-center gap-1">
                      <Clock className="h-3 w-3" aria-hidden />
                      {m.est_min} min
                    </span>
                  </div>
                </div>

                <div className="flex shrink-0 flex-wrap gap-2">
                  <Link
                    href={`/prep?module=${m.id}`}
                    className="no-underline"
                    aria-label={`Start module: ${m.title}`}
                  >
                    <Button size="sm" variant="ink">
                      Start
                      <ArrowRight className="h-3.5 w-3.5" aria-hidden />
                    </Button>
                  </Link>
                  <Link
                    href={`/setup?focus=${encodeURIComponent(m.competency)}`}
                    className="no-underline"
                    aria-label={`Practice ${m.competency} in a mock interview`}
                  >
                    <Button size="sm" variant="out">
                      Practice in a mock
                    </Button>
                  </Link>
                </div>
              </CardContent>
            </Card>
          </li>
        ))}
      </ol>
    </section>
  );
}
