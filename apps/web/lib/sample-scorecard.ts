import {
  ScoreCardSchema,
  SAMPLE_INTERVIEW_CONTEXT,
  type ScoreCard,
} from "@deepinterview/shared";

/**
 * A realistic, varied, VALID sample ScoreCard used as the offline fallback for
 * the report screen (and the "Preview (sample data)" state). All scores are on
 * the spec's 0-5 scale (overall, per-competency, fluency, clarity). It passes
 * `ScoreCardSchema.parse(SAMPLE_SCORECARD)` — see the parse call at the bottom,
 * which throws at import time if this ever drifts out of contract.
 *
 * NOTE: the shared `SAMPLE_INTERVIEW_CONTEXT.scorecard` uses a different
 * (0-100 / 0-1) scale; we intentionally do NOT reuse it for scoring. We reuse
 * the shared context ONLY for the transcript (question text + answer), which is
 * scale-independent.
 */
export const SAMPLE_SCORECARD: ScoreCard = {
  overall_score: 3.6,
  competency_scores: [
    {
      competency: "Communication",
      score: 4.2,
      evidence:
        "Structured answers with clear signposting; summarized takeaways before moving on.",
      level: "strong",
    },
    {
      competency: "Technical Depth",
      score: 4.5,
      evidence:
        "Explained exactly-once semantics and consumer-rebalance recovery without prompting.",
      level: "strong",
    },
    {
      competency: "System Design",
      score: 3.3,
      evidence:
        "Solid component breakdown, but glossed over capacity estimates and failure modes.",
      level: "solid",
    },
    {
      competency: "Leadership",
      score: 2.4,
      evidence:
        "Stories stayed within the immediate team; little evidence of org-wide influence.",
      level: "developing",
    },
    {
      competency: "Behavioral / STAR",
      score: 1.8,
      evidence:
        "Answers jumped to the result; the situation and task framing were often skipped.",
      level: "weak",
    },
  ],
  strengths: [
    "Deep, confident distributed-systems knowledge",
    "Calm, well-paced delivery under follow-up pressure",
    "Quantifies impact with concrete metrics",
  ],
  weaknesses: [
    "STAR structure is inconsistent — situation and task are often dropped",
    "Leadership examples rarely reach beyond the immediate team",
    "Capacity and failure-mode reasoning is thin in system-design answers",
  ],
  weak_competencies: ["Behavioral / STAR", "Leadership"],
  model_answers: [
    {
      question_id: "q1",
      answer:
        "Situation: our three platform teams each shipped to prod differently, causing weekly incidents. Task: I was asked to align them on one deployment standard within a quarter. Action: I ran a working group, wrote an RFC, piloted it on my own service, then drove adoption with a migration guide and office hours. Result: 120 services moved over, incident rate dropped 40%, and the standard is now the default. The cross-team part was the hardest — I won buy-in by letting each team keep one escape hatch.",
    },
    {
      question_id: "q2",
      answer:
        "I'd use idempotent producers and a Kafka transaction that writes the settlement and its offset atomically, plus a dedup store keyed by event id with a TTL longer than the max retry window. On a rebalance mid-batch, the in-flight transaction aborts and the new owner reprocesses from the last committed offset — the dedup store absorbs the replay. I'd trade a little latency (batched commits) for durability, and expose a reconciliation job to catch any poison messages.",
    },
  ],
  next_steps: [
    "Drill the STAR frame: open every behavioral answer with one sentence of Situation + Task.",
    "Prepare two stories that show influence across teams or orgs, not just within your squad.",
    "Practice back-of-the-envelope capacity math out loud for system-design rounds.",
  ],
  language_report: {
    fluency_score: 4.1,
    filler_word_count: 14,
    clarity_score: 3.9,
    code_switching_notes:
      "Occasional switch to Vietnamese for emphasis on a few terms; did not impede comprehension.",
    pronunciation_notes:
      "Clear overall; minor stress drift on long multi-syllable technical terms.",
    summary:
      "Fluent, well-paced English with controlled code-switching. Trimming filler words ('like', 'you know') would sharpen otherwise crisp delivery.",
  },
  summary:
    "A strong technical interview let down by storytelling structure. The candidate's systems depth and communication are interview-ready; the clear growth areas are STAR discipline on behavioral questions and demonstrating leadership impact beyond the immediate team.",
};

/**
 * Minimal transcript material for the report's transcript section. We reuse the
 * shared `SAMPLE_INTERVIEW_CONTEXT` for the question plan + answers (flattening
 * the localized `{en, vi}` question text to EN and joining answers by
 * `question_id`), so the offline report shows a realistic playback list.
 */
const ctx = SAMPLE_INTERVIEW_CONTEXT;

export interface SampleInterviewQuestion {
  id: string;
  text: string;
}

export interface SampleInterviewAnswer {
  question_id: string;
  transcript: string;
}

export interface SampleInterview {
  company: string;
  role: string;
  questions: SampleInterviewQuestion[];
  answers: SampleInterviewAnswer[];
}

export const SAMPLE_INTERVIEW: SampleInterview = {
  company: ctx.job.company_name,
  role: ctx.job.title,
  questions: ctx.plan.questions.map((q) => ({
    id: q.id,
    // Schema guarantees a non-empty `en`; coalesce only to satisfy
    // noUncheckedIndexedAccess.
    text: q.text.en ?? "",
  })),
  answers: [
    // From the shared context (q1 is the only answered turn there)...
    ...ctx.answers.map((a) => ({
      question_id: a.question_id,
      transcript: a.transcript,
    })),
    // ...supplemented so the second planned question also shows a turn.
    {
      question_id: "q2",
      transcript:
        "So for exactly-once on Kafka, I'd lean on idempotent producers and transactions, and keep a dedup store keyed by the event id. On a rebalance the in-flight transaction just aborts and the next consumer replays from the committed offset, and the dedup store catches the duplicate. The tradeoff is a bit of latency from batching commits, which is fine for settlement.",
    },
  ],
};

// Fail loudly at import if the sample ever drifts out of contract.
ScoreCardSchema.parse(SAMPLE_SCORECARD);
