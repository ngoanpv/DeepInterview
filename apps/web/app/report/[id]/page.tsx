import Link from "next/link";
import { redirect } from "next/navigation";
import {
  ScoreCardSchema,
  InterviewContextSchema,
  type ScoreCard,
  type InterviewContext,
} from "@deepinterview/shared";
import { isSupabaseConfigured } from "@/lib/env";
import { createClient, getUser } from "@/lib/supabase/server";
import { SAMPLE_SCORECARD, SAMPLE_INTERVIEW } from "@/lib/sample-scorecard";
import { Eyebrow } from "@/components/ui/eyebrow";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ScoreBento } from "@/components/report/score-bento";
import { CompetencyChart } from "@/components/report/competency-chart";
import { LanguageReportCard } from "@/components/report/language-report-card";
import { StrengthsGaps } from "@/components/report/strengths-gaps";
import { ModelAnswers } from "@/components/report/model-answers";
import {
  TranscriptSection,
  type TranscriptTurn,
} from "@/components/report/transcript-section";

// Reads server-only config and a per-request DB row; never prerender.
export const dynamic = "force-dynamic";

interface Loaded {
  scorecard: ScoreCard;
  /** Parsed interview context for the real row, when present. */
  context: InterviewContext | null;
  isSample: boolean;
  company: string | null;
  role: string | null;
}

/**
 * Resolve the scorecard for this session. When Supabase is configured we fetch
 * the `sessions` row and zod-parse `row.scorecard` (+ `row.context` for the
 * transcript); on any miss — unconfigured, no row, bad shape — we fall back to
 * the sample so the report always renders (offline-safe).
 */
async function load(id: string): Promise<Loaded> {
  const fallback: Loaded = {
    scorecard: SAMPLE_SCORECARD,
    context: null,
    isSample: true,
    company: SAMPLE_INTERVIEW.company,
    role: SAMPLE_INTERVIEW.role,
  };

  if (!isSupabaseConfigured()) return fallback;

  const supabase = await createClient();
  if (!supabase) return fallback;

  const { data, error } = await supabase
    .from("sessions")
    .select("scorecard, context, company")
    .eq("id", id)
    .maybeSingle();

  if (error || !data) return fallback;

  const parsed = ScoreCardSchema.safeParse(data.scorecard);
  if (!parsed.success) return fallback;

  const ctxParsed = InterviewContextSchema.safeParse(data.context);
  const context = ctxParsed.success ? ctxParsed.data : null;

  return {
    scorecard: parsed.data,
    context,
    isSample: false,
    company: context?.job.company_name ?? data.company ?? null,
    role: context?.job.title ?? null,
  };
}

/** Build the question-text lookup + ordered transcript turns. */
function buildTranscript(loaded: Loaded): {
  questionText: Record<string, string>;
  turns: TranscriptTurn[];
} {
  const questionText: Record<string, string> = {};
  const turns: TranscriptTurn[] = [];

  if (loaded.context) {
    const answerByQ = new Map(
      loaded.context.answers.map((a) => [a.question_id, a.transcript]),
    );
    for (const q of loaded.context.plan.questions) {
      // Schema guarantees a non-empty `en`; coalesce for noUncheckedIndexedAccess.
      const text = q.text.en ?? "";
      questionText[q.id] = text;
      turns.push({
        question_id: q.id,
        question: text,
        transcript: answerByQ.get(q.id) ?? null,
      });
    }
  } else {
    const answerByQ = new Map(
      SAMPLE_INTERVIEW.answers.map((a) => [a.question_id, a.transcript]),
    );
    for (const q of SAMPLE_INTERVIEW.questions) {
      questionText[q.id] = q.text;
      turns.push({
        question_id: q.id,
        question: q.text,
        transcript: answerByQ.get(q.id) ?? null,
      });
    }
  }

  return { questionText, turns };
}

export default async function ReportPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  // Page-level auth: gate only when Supabase is wired up; offline we proceed.
  if (isSupabaseConfigured()) {
    const user = await getUser();
    if (!user) redirect("/login");
  }

  const loaded = await load(id);
  const { scorecard } = loaded;
  const { questionText, turns } = buildTranscript(loaded);

  return (
    <main className="mx-auto max-w-[920px] px-6 py-12">
      {/* Header */}
      <header className="flex items-center justify-between">
        <Link href="/" className="no-underline">
          <Eyebrow>DeepInterview</Eyebrow>
        </Link>
        {loaded.isSample && (
          <Badge variant="outline">Preview (sample data)</Badge>
        )}
      </header>

      <div className="mt-6">
        <h1 className="font-serif text-4xl text-ink">Your interview report</h1>
        <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-muted">
          {loaded.role && loaded.company ? (
            <>
              {loaded.role} · {loaded.company}.{" "}
            </>
          ) : null}
          {scorecard.summary}
        </p>
      </div>

      {/* Bento: hero + top metrics */}
      <section className="mt-8">
        <ScoreBento scorecard={scorecard} />
      </section>

      {/* Competency radar + strengths/gaps */}
      <section className="mt-4 grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Competencies</CardTitle>
            <CardDescription>Scored 0–5 across the rubric.</CardDescription>
          </CardHeader>
          <CardContent className="pb-6">
            <CompetencyChart competencies={scorecard.competency_scores} />
          </CardContent>
        </Card>

        <div className="lg:col-span-3">
          <StrengthsGaps scorecard={scorecard} />
        </div>
      </section>

      {/* Language report + next steps */}
      <section className="mt-4 grid gap-4 md:grid-cols-2">
        <LanguageReportCard report={scorecard.language_report} />
        <Card>
          <CardHeader>
            <CardTitle>Next steps</CardTitle>
            <CardDescription>
              What to drill before your next run.
            </CardDescription>
          </CardHeader>
          <CardContent className="pb-6">
            <ol className="space-y-3">
              {scorecard.next_steps.map((step, i) => (
                <li
                  key={i}
                  className="flex gap-3 text-sm leading-relaxed text-ink-soft"
                >
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent-soft font-mono text-[11px] text-accent">
                    {i + 1}
                  </span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      </section>

      {/* Stronger answers */}
      <section className="mt-4">
        <ModelAnswers
          answers={scorecard.model_answers}
          questionText={questionText}
        />
      </section>

      {/* Transcript */}
      <section className="mt-4">
        <TranscriptSection turns={turns} />
      </section>

      {/* CTA */}
      <section className="mt-4">
        <Card className="bg-accent-soft">
          <CardContent className="flex flex-col items-start gap-4 py-6 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="font-serif text-xl text-ink">
                Turn these gaps into a study plan
              </h2>
              <p className="mt-1 text-sm text-muted">
                Your Prep Coach builds focused drills around your weak areas —
                then you run it back.
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap gap-3">
              <Link href="/prep" className="no-underline">
                <Button variant="ink">Coach me on my weak areas</Button>
              </Link>
              <Link href="/setup" className="no-underline">
                <Button variant="out">Practice again</Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </section>
    </main>
  );
}
