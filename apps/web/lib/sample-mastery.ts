/**
 * Offline sample data for the Prep Coach (/prep). Everything here is STATIC —
 * no `Date.now()`/`Math.random()` at module scope — because this module is
 * imported by both the server render and the client island; any clock or random
 * value would diverge between the two passes and trip a hydration mismatch.
 *
 * The closed loop: an interview scorecard names `weak_competencies` (here:
 * "Behavioral / STAR", "Leadership", plus thin System Design / Kafka depth) →
 * the coach turns those gaps into an ordered study plan, a prerequisite mastery
 * graph, and a flashcard deck — then loops the learner back into a new mock.
 */

/** Mastery state for a study module / competency node. */
export type MasteryState = "unseen" | "learning" | "shaky" | "mastered";

/** One ordered step in the gap → path study plan. */
export interface StudyModule {
  id: string;
  title: string;
  /** The shared-entity competency this module strengthens. */
  competency: string;
  status: MasteryState;
  /** Estimated focused minutes for the module. */
  est_min: number;
  /** One-line "why this is here" tied to the interview gap. */
  rationale: string;
}

/**
 * Ordered modules derived from the last interview's weak areas. Sequenced so
 * fundamentals (STAR frame, leadership stories) come before the deeper
 * system-design / Kafka drills.
 */
export const SAMPLE_STUDY_PLAN: StudyModule[] = [
  {
    id: "m1",
    title: "The STAR frame, drilled",
    competency: "Behavioral / STAR",
    status: "shaky",
    est_min: 20,
    rationale:
      "Your answers jumped to the result — open with Situation + Task.",
  },
  {
    id: "m2",
    title: "Leadership stories beyond your squad",
    competency: "Leadership",
    status: "learning",
    est_min: 25,
    rationale:
      "Examples stayed within the immediate team; show org-wide influence.",
  },
  {
    id: "m3",
    title: "System design: capacity & failure modes",
    competency: "System Design",
    status: "shaky",
    est_min: 30,
    rationale: "Capacity math and failure reasoning were thin under follow-up.",
  },
  {
    id: "m4",
    title: "Kafka exactly-once, end to end",
    competency: "Kafka",
    status: "learning",
    est_min: 25,
    rationale:
      "Solidify idempotent producers, transactions, and rebalance recovery.",
  },
  {
    id: "m5",
    title: "Back-of-envelope estimation out loud",
    competency: "System Design",
    status: "unseen",
    est_min: 20,
    rationale:
      "Practice narrating throughput / storage estimates in real time.",
  },
];

/** A competency entity in the mastery graph. */
export interface MasteryNode {
  id: string;
  label: string;
  state: MasteryState;
  /** Layout hint (xyflow position). */
  x: number;
  y: number;
}

/** A prerequisite edge: `source` should be learned before `target`. */
export interface MasteryEdge {
  id: string;
  source: string;
  target: string;
}

export interface MasteryGraph {
  nodes: MasteryNode[];
  edges: MasteryEdge[];
}

/**
 * Prerequisite graph over the candidate's competency entities. Colors are
 * assigned downstream from `state`. Layout is a hand-placed left→right DAG so
 * the read-only graph stays calm and legible without a layout engine.
 */
export const SAMPLE_MASTERY_GRAPH: MasteryGraph = {
  nodes: [
    { id: "comm", label: "Communication", state: "mastered", x: 0, y: 40 },
    { id: "star", label: "Behavioral / STAR", state: "shaky", x: 260, y: 0 },
    { id: "leadership", label: "Leadership", state: "learning", x: 520, y: 0 },
    {
      id: "fundamentals",
      label: "Systems Fundamentals",
      state: "mastered",
      x: 0,
      y: 200,
    },
    { id: "sysdesign", label: "System Design", state: "shaky", x: 260, y: 200 },
    { id: "kafka", label: "Kafka", state: "learning", x: 520, y: 160 },
    {
      id: "scaling",
      label: "Scaling & Capacity",
      state: "unseen",
      x: 520,
      y: 280,
    },
  ],
  edges: [
    { id: "e-comm-star", source: "comm", target: "star" },
    { id: "e-star-leadership", source: "star", target: "leadership" },
    { id: "e-fund-sysdesign", source: "fundamentals", target: "sysdesign" },
    { id: "e-sysdesign-kafka", source: "sysdesign", target: "kafka" },
    { id: "e-sysdesign-scaling", source: "sysdesign", target: "scaling" },
    { id: "e-comm-sysdesign", source: "comm", target: "sysdesign" },
  ],
};

/** A two-sided review card tied to a competency. */
export interface Flashcard {
  id: string;
  front: string;
  back: string;
  competency: string;
}

/**
 * Spaced-repetition deck seeded from the weak areas. Static content only — the
 * scheduler state (ease/interval/due) is created at runtime inside the client
 * island, never here.
 */
export const SAMPLE_FLASHCARDS: Flashcard[] = [
  {
    id: "f1",
    front: "What are the four parts of a STAR answer?",
    back: "Situation, Task, Action, Result. Open with one sentence of Situation + Task so the interviewer has context before the result.",
    competency: "Behavioral / STAR",
  },
  {
    id: "f2",
    front: "How do you show leadership impact beyond your immediate team?",
    back: "Pick a story where you drove a change across teams/orgs: an RFC, a working group, or a standard others adopted — and quantify the reach (e.g. 120 services migrated).",
    competency: "Leadership",
  },
  {
    id: "f3",
    front: "Kafka: how do you achieve exactly-once delivery?",
    back: "Idempotent producers + a transaction that writes the record and its offset atomically, plus a dedup store keyed by event id with a TTL longer than the max retry window.",
    competency: "Kafka",
  },
  {
    id: "f4",
    front:
      "A consumer rebalances mid-batch — what happens to an in-flight transaction?",
    back: "It aborts. The new partition owner reprocesses from the last committed offset; the dedup store absorbs the replay so no duplicates land.",
    competency: "Kafka",
  },
  {
    id: "f5",
    front: "System design: what do you estimate before drawing boxes?",
    back: "Back-of-envelope load: QPS (read/write), data volume & growth, and the storage/bandwidth that implies — out loud — so capacity drives the design, not the reverse.",
    competency: "System Design",
  },
  {
    id: "f6",
    front: "Name two failure modes to call out in a system-design answer.",
    back: "e.g. a hot partition / thundering herd on cache miss, and a downstream dependency timeout — pair each with a mitigation (sharding key choice, circuit breaker + backoff).",
    competency: "System Design",
  },
];
