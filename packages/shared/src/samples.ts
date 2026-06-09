import type { InterviewContext } from "./interview-context";

export const SAMPLE_INTERVIEW_CONTEXT: InterviewContext = {
  session_id: "sess_01HZX9K2QWERTYUIOP",
  candidate: {
    name: "Mai Nguyen",
    headline: "Senior Backend Engineer · Distributed Systems",
    summary_120w:
      "Mai is a senior backend engineer with eight years building high-throughput payment and messaging systems in Go and Python. She has led the redesign of a ledger service handling 40k requests per second, mentored four engineers, and owns the on-call rotation for a multi-region Kubernetes platform. She cares about correctness, observability, and pragmatic API design, and has shipped event-driven pipelines on Kafka with exactly-once semantics.",
    years_experience: 8,
    seniority: "senior",
    skills: [
      "Go",
      "Python",
      "Kafka",
      "PostgreSQL",
      "Kubernetes",
      "gRPC",
      "Redis",
    ],
    projects: [
      {
        name: "Ledger Rewrite",
        description:
          "Rebuilt a monolithic ledger into an event-sourced service with exactly-once Kafka processing.",
        tech: ["Go", "Kafka", "PostgreSQL"],
      },
      {
        name: "Multi-region Messaging",
        description:
          "Designed an active-active messaging backbone across three cloud regions.",
        tech: ["Python", "Redis", "gRPC"],
      },
    ],
    achievements: [
      "Cut p99 ledger latency from 380ms to 70ms",
      "Led migration of 120 services to a shared Kubernetes platform",
    ],
    education: [
      {
        institution: "Hanoi University of Science and Technology",
        degree: "BSc Computer Science",
        field: "Computer Science",
        year: 2016,
      },
    ],
    spoken_languages: ["Vietnamese", "English"],
    links: [
      "https://github.com/mai-nguyen",
      "https://linkedin.com/in/mai-nguyen",
    ],
  },
  job: {
    title: "Staff Backend Engineer",
    company_name: "Acme Payments",
    location: "Remote (EU)",
    seniority: "staff",
    must_have: ["Go", "Distributed systems", "Event-driven architecture"],
    nice_to_have: ["Kafka", "Kubernetes", "Payments domain"],
    responsibilities: [
      "Own the core ledger and settlement platform",
      "Set technical direction for the payments org",
      "Mentor senior and mid-level engineers",
    ],
    tech_stack: ["Go", "Kafka", "PostgreSQL", "Kubernetes", "gRPC"],
    raw_text:
      "Acme Payments is hiring a Staff Backend Engineer to own our core ledger and settlement platform. You will set technical direction, design event-driven systems, and mentor the team. Strong Go and distributed systems experience required.",
  },
  company: {
    name: "Acme Payments",
    summary:
      "Acme Payments provides embedded payment and ledger infrastructure for fintech companies across Europe.",
    industry: "Fintech / Payments",
    tech_stack: ["Go", "Kafka", "PostgreSQL", "Kubernetes"],
    values: ["Correctness over speed", "Ownership", "Customer obsession"],
    interview_process: [
      "Recruiter screen",
      "Technical phone screen",
      "System design interview",
      "Onsite loop",
    ],
    recent_news: [
      "Raised a $60M Series C in early 2026",
      "Launched real-time settlement product in the EU",
    ],
    citations: [
      {
        title: "Acme Payments raises Series C",
        url: "https://example.com/acme-series-c",
        snippet:
          "Acme Payments announced a $60M Series C to expand its ledger platform.",
      },
    ],
  },
  gap: {
    strengths: [
      "Deep Go expertise",
      "Event-driven systems",
      "Payments domain familiarity",
    ],
    gaps: ["Limited org-wide technical leadership at staff scope"],
    probe_targets: [
      "Cross-team technical influence",
      "Settlement system tradeoffs",
    ],
    matched_skills: ["Go", "Kafka", "Kubernetes", "PostgreSQL"],
    missing_skills: ["Formal staff-level org leadership"],
    summary:
      "Strong technical match on the engineering core; main probe area is staff-scope leadership and cross-team influence.",
  },
  plan: {
    sections_order: ["intro", "behavioral", "technical", "coding", "wrap"],
    questions: [
      {
        id: "q1",
        section: "behavioral",
        text: {
          en: "Tell me about a time you drove a technical decision across multiple teams.",
          vi: "Hãy kể về một lần bạn dẫn dắt một quyết định kỹ thuật giữa nhiều nhóm.",
        },
        difficulty: 3,
        rubric: [
          {
            criterion: "Scope of influence",
            weight: 0.5,
            description: "Demonstrates impact beyond their immediate team.",
          },
          {
            criterion: "Decision quality",
            weight: 0.5,
            description: "Shows sound reasoning and tradeoff analysis.",
          },
        ],
        followups: ["How did you handle disagreement?"],
        target_competency: "technical_leadership",
      },
      {
        id: "q2",
        section: "technical",
        text: {
          en: "How would you design an exactly-once settlement pipeline on Kafka?",
          vi: "Bạn sẽ thiết kế một pipeline thanh toán đúng-một-lần trên Kafka như thế nào?",
        },
        difficulty: 4,
        rubric: [
          {
            criterion: "Correctness",
            weight: 0.6,
            description: "Handles idempotency and failure recovery correctly.",
          },
          {
            criterion: "Tradeoffs",
            weight: 0.4,
            description: "Discusses latency vs durability tradeoffs.",
          },
        ],
        followups: ["What happens on a consumer rebalance mid-batch?"],
        target_competency: "distributed_systems",
      },
    ],
    time_budget_min: 15,
    language_mode: {
      primary: "en",
      mixed: true,
    },
  },
  cursor: 1,
  answers: [
    {
      question_id: "q1",
      transcript:
        "I led the migration of our services to a shared platform, aligning three teams on a common deployment standard...",
      started_at: "2026-06-08T09:00:00Z",
      ended_at: "2026-06-08T09:03:30Z",
      duration_sec: 210,
      followups_asked: ["How did you handle disagreement?"],
    },
  ],
  scorecard: {
    overall_score: 78.5,
    coverage_pct: 1.0,
    competency_scores: [
      {
        competency: "technical_leadership",
        score: 72,
        evidence:
          "Drove a multi-team platform migration but stayed mostly within engineering.",
        level: "solid",
      },
      {
        competency: "distributed_systems",
        score: 88,
        evidence:
          "Clear grasp of exactly-once semantics and rebalance handling.",
        level: "strong",
      },
    ],
    strengths: ["Distributed systems depth", "Clear communication"],
    weaknesses: ["Staff-scope org influence"],
    weak_competencies: ["technical_leadership"],
    model_answers: [
      {
        question_id: "q2",
        answer:
          "Use idempotent producers, transactional writes, and a deduplication store keyed by event id to guarantee exactly-once settlement.",
      },
    ],
    next_steps: [
      "Practice framing cross-org influence stories",
      "Review settlement reconciliation patterns",
    ],
    language_report: {
      fluency_score: 0.86,
      filler_word_count: 12,
      clarity_score: 0.82,
      code_switching_notes:
        "Occasional switch to Vietnamese for emphasis; did not impede clarity.",
      pronunciation_notes:
        "Clear; minor stress on multi-syllable technical terms.",
      summary:
        "Fluent and clear English with comfortable, controlled code-switching.",
    },
    summary:
      "Strong technical candidate; main growth area is demonstrating staff-level organizational leadership.",
  },
};
