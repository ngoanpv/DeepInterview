import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { type ScoreCard, type InterviewContext } from "@deepinterview/shared";
import { serverEnv } from "@/lib/env";
import { SessionViewSchema } from "@/lib/session";
import { SAMPLE_SCORECARD, SAMPLE_INTERVIEW } from "@/lib/sample-scorecard";
import { Eyebrow } from "@/components/ui/eyebrow";
import { Badge } from "@/components/ui/badge";
import { buttonClasses } from "@/components/ui/button";
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
import { ScoringPoll } from "@/components/report/scoring-poll";
import {
  TranscriptSection,
  type TranscriptTurn,
} from "@/components/report/transcript-section";

// Reads server-only config and calls the agent API per request; never prerender.
export const dynamic = "force-dynamic";

/**
 * - `ready`   real scorecard persisted → full report (possibly `degraded`).
 * - `sample`  agent unreachable / unknown session → sample preview.
 * - `empty`   interview produced no answers (status `no_answers`, or a legacy
 *             `complete` row with a blank card) → honest empty state, NOT zeros.
 * - `scoring` interview done but scoring hasn't produced a card yet → poll.
 * - `error`   session errored (scoring failed — retriable) → honest notice.
 */
type ReportState = "ready" | "sample" | "empty" | "scoring" | "error";

interface Loaded {
  state: ReportState;
  scorecard: ScoreCard;
  /**
   * The agent deliberately persists degraded cards (numbers-only when the
   * narrative LLM call fails — see the agent's `_degraded_scorecard`). When the
   * persisted card is missing its narrative (or its scores), we still render
   * the report but flag it so the page shows an honest partial-report notice.
   */
  degraded: boolean;
  context: InterviewContext | null;
  company: string | null;
  role: string | null;
}

/**
 * Resolve the report state by reading the agent API
 * (`GET /api/session/{id}` → SessionView, which carries `scorecard` + `context`).
 * The sample preview is used ONLY on a true miss (agent down / unknown session /
 * shape drift). A real session with no answers resolves to `empty` (never a
 * misleading all-zeros card), and an in-flight session resolves to `scoring`.
 */
async function load(id: string): Promise<Loaded> {
  const sample: Loaded = {
    state: "sample",
    scorecard: SAMPLE_SCORECARD,
    degraded: false,
    context: null,
    company: SAMPLE_INTERVIEW.company,
    role: SAMPLE_INTERVIEW.role,
  };

  try {
    const res = await fetch(
      `${serverEnv.agentApiUrl}/api/session/${encodeURIComponent(id)}`,
      { cache: "no-store", signal: AbortSignal.timeout(15_000) },
    );
    if (!res.ok) return sample;

    const parsed = SessionViewSchema.safeParse(await res.json());
    if (!parsed.success) return sample;

    const view = parsed.data;
    const base = {
      degraded: false,
      context: view.context,
      company: view.context?.job.company_name ?? null,
      role: view.context?.job.title ?? null,
    };
    const answers = view.context?.answers.length ?? 0;
    const hasScores = (view.scorecard?.competency_scores?.length ?? 0) > 0;

    // Honest empty: no answers were captured. New sessions are flagged
    // `no_answers`; legacy rows may be `complete` with a blank (score-less) card.
    if (
      view.status === "no_answers" ||
      (answers === 0 && !!view.scorecard && !hasScores)
    ) {
      return { ...base, state: "empty", scorecard: SAMPLE_SCORECARD };
    }
    // `error` now also covers a scoring (evaluate) failure for an answered
    // interview — retriable, so the error copy invites a re-run.
    if (view.status === "error" || view.status === "rejected") {
      return { ...base, state: "error", scorecard: SAMPLE_SCORECARD };
    }
    // A persisted card ALWAYS renders — the agent deliberately writes degraded
    // (numbers-only / narrative-less) cards, and a `complete` session is
    // terminal: polling it forever would never change anything. Flag partial
    // cards so the page shows an honest notice instead of silent blanks.
    if (view.scorecard && (hasScores || view.status === "complete")) {
      const c = view.scorecard;
      const narrativeMissing =
        c.strengths.length === 0 &&
        c.weaknesses.length === 0 &&
        c.model_answers.length === 0;
      return {
        ...base,
        state: "ready",
        scorecard: c,
        degraded: !hasScores || narrativeMissing,
      };
    }
    // `complete` but no card at all (partial/legacy write): terminal — treat as
    // a retriable scoring error rather than polling forever.
    if (view.status === "complete") {
      return { ...base, state: "error", scorecard: SAMPLE_SCORECARD };
    }
    // Interview not scored yet — poll until a terminal state arrives.
    return { ...base, state: "scoring", scorecard: SAMPLE_SCORECARD };
  } catch {
    return sample;
  }
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

/** Shared page chrome for the non-report (status) states. */
function StatusShell({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto max-w-[920px] px-6 py-12">
      <header className="flex items-center justify-between">
        <Link href="/" className="no-underline">
          <Eyebrow>DeepInterview</Eyebrow>
        </Link>
      </header>
      <div className="mt-16 flex justify-center">{children}</div>
    </main>
  );
}

export default async function ReportPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  // No auth gate: OSS reads the report through the agent API, which needs no
  // sign-in. (Hosted/multi-tenant deployments add auth as a separate layer.)
  const loaded = await load(id);

  // Still scoring: show a calm waiting state and auto-refresh until terminal.
  if (loaded.state === "scoring") {
    return (
      <StatusShell>
        <ScoringPoll />
        <Card className="max-w-md text-center">
          <CardContent className="flex flex-col items-center gap-3 py-10">
            <span
              className="h-7 w-7 animate-spin rounded-full border-2 border-accent border-t-transparent"
              aria-hidden
            />
            <h1 className="font-serif text-2xl text-ink">
              Scoring your interview…
            </h1>
            <p className="max-w-sm text-sm leading-relaxed text-muted">
              Hang tight — we’re analyzing your answers. This page updates
              automatically the moment your report is ready.
            </p>
          </CardContent>
        </Card>
      </StatusShell>
    );
  }

  // No answers captured: honest empty state instead of an all-zeros report.
  if (loaded.state === "empty") {
    return (
      <StatusShell>
        <Card className="max-w-md text-center">
          <CardContent className="flex flex-col items-center gap-4 py-10">
            <h1 className="font-serif text-2xl text-ink">
              No answers recorded
            </h1>
            <p className="max-w-sm text-sm leading-relaxed text-muted">
              {loaded.role && loaded.company ? (
                <>
                  This {loaded.role} interview at {loaded.company} ended before
                  any question was answered, so there’s nothing to score
                  yet.{" "}
                </>
              ) : (
                <>
                  This interview ended before any question was answered, so
                  there’s nothing to score yet.{" "}
                </>
              )}
              Give it another go — answer out loud and we’ll build your report.
            </p>
            <div className="flex flex-wrap justify-center gap-3">
              <Link href="/setup" className={buttonClasses()}>
                Practice again
              </Link>
              <Link href="/" className={buttonClasses({ variant: "out" })}>
                Back home
              </Link>
            </div>
          </CardContent>
        </Card>
      </StatusShell>
    );
  }

  // Session errored — scoring failed before a card was saved. The agent keeps
  // the session's answers, so scoring is retriable; be honest, don't fake zeros.
  if (loaded.state === "error") {
    return (
      <StatusShell>
        <Card className="max-w-md text-center">
          <CardContent className="flex flex-col items-center gap-4 py-10">
            <h1 className="font-serif text-2xl text-ink">
              We couldn’t score this interview
            </h1>
            <p className="max-w-sm text-sm leading-relaxed text-muted">
              Scoring hit a temporary error, so we’re not showing a report
              rather than show inaccurate results. Your answers are saved and
              scoring can be retried — check back here in a few minutes, or
              start another run.
            </p>
            <div className="flex flex-wrap justify-center gap-3">
              <Link
                href={`/report/${encodeURIComponent(id)}`}
                className={buttonClasses()}
              >
                Check again
              </Link>
              <Link href="/setup" className={buttonClasses({ variant: "out" })}>
                Practice again
              </Link>
            </div>
          </CardContent>
        </Card>
      </StatusShell>
    );
  }

  // ready | sample → the full report.
  const { scorecard } = loaded;
  const { questionText, turns } = buildTranscript(loaded);

  return (
    <main className="mx-auto max-w-[920px] px-6 py-12">
      {/* Header */}
      <header className="flex items-center justify-between">
        <Link href="/" className="no-underline">
          <Eyebrow>DeepInterview</Eyebrow>
        </Link>
        {loaded.state === "sample" && (
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

      {/* Partial (degraded) card: the agent persisted it without the full
          narrative — show what's there, with an honest notice. */}
      {loaded.degraded && (
        <div className="mt-6 flex items-start gap-2 rounded-[10px] border border-line bg-accent-soft px-3.5 py-2.5 text-[13px] leading-relaxed text-ink-soft">
          <AlertTriangle
            className="mt-0.5 h-4 w-4 shrink-0 text-accent"
            aria-hidden
          />
          <span>
            Partial report: the detailed narrative was unavailable when this
            interview was scored. Your scores are preserved — re-run scoring to
            get the full write-up and model answers.
          </span>
        </div>
      )}

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
              <Link
                // Pass the session so the Prep Coach builds from THIS report's
                // real scorecard (the sample preview links plain /prep).
                href={
                  loaded.state === "ready"
                    ? `/prep?session=${encodeURIComponent(id)}`
                    : "/prep"
                }
                className={buttonClasses()}
              >
                Coach me on my weak areas
              </Link>
              <Link href="/setup" className={buttonClasses({ variant: "out" })}>
                Practice again
              </Link>
            </div>
          </CardContent>
        </Card>
      </section>
    </main>
  );
}
