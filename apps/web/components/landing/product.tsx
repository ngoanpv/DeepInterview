import { Container } from "@/components/ui/container";
import { Eyebrow } from "@/components/ui/eyebrow";
import { Reveal } from "@/components/ui/reveal";
import { FeatureRow } from "@/components/landing/feature-row";

const LANGUAGES = [
  { label: "English", active: true },
  { label: "Tiếng Việt" },
  { label: "Español" },
  { label: "हिन्दी" },
  { label: "Bahasa" },
  { label: "Português" },
  { label: "Filipino" },
  { label: "Français" },
  { label: "+ more" },
];

const PLAN_ROWS: { label: string; tag: string; strong: boolean }[] = [
  { label: "Distributed systems", tag: "probe", strong: true },
  { label: "Kafka & event streaming", tag: "gap", strong: true },
  { label: "System design — payments", tag: "core", strong: false },
  { label: "Behavioral — ownership", tag: "core", strong: false },
  { label: "SQL window functions", tag: "warm-up", strong: false },
];

const LOOP_STEPS = [
  { badge: "1", label: "CV + JD → gap analysis" },
  { badge: "2", label: "Study plan for weak areas" },
  { badge: "3", label: "Voice mock interview" },
  { badge: "4", label: "Scored feedback" },
  { badge: "↻", label: "back to step 2, sharper" },
];

function LanguagesVisual() {
  return (
    <div>
      <div className="mb-3 font-mono text-[11px] uppercase tracking-[0.06em] text-faint">
        LANGUAGES
      </div>
      <div className="flex flex-wrap gap-2">
        {LANGUAGES.map((lang) => (
          <span
            key={lang.label}
            className={
              lang.active
                ? "rounded-lg border border-ink px-[11px] py-1.5 text-[13px] font-medium text-ink"
                : "rounded-lg border border-line bg-[#FCFBF9] px-[11px] py-1.5 text-[13px] text-ink-soft"
            }
          >
            {lang.label}
          </span>
        ))}
      </div>
      <div className="mt-[18px] text-[13.5px] text-muted">
        English-first, with first-class interviews in your own language — drill
        the same role in both.
      </div>
    </div>
  );
}

function PlanVisual() {
  return (
    <div>
      <div className="mb-2.5 font-mono text-[11px] uppercase tracking-[0.06em] text-faint">
        QUESTION PLAN · SENIOR BACKEND
      </div>
      {PLAN_ROWS.map((row) => (
        <div
          key={row.label}
          className="flex justify-between border-b border-dashed border-line-2 py-2.5 text-[13.5px] last:border-b-0"
        >
          <span>{row.label}</span>
          <span className={row.strong ? "font-semibold text-ok" : "text-muted"}>
            {row.tag}
          </span>
        </div>
      ))}
    </div>
  );
}

function LoopVisual() {
  return (
    <div className="flex flex-col gap-2.5">
      {LOOP_STEPS.map((step) => (
        <div
          key={step.badge}
          className="flex items-center gap-[11px] text-[13.5px] text-ink-soft"
        >
          <span className="grid h-[26px] w-[26px] place-items-center rounded-[7px] border border-line font-mono text-[11px] text-accent">
            {step.badge}
          </span>
          {step.label}
        </div>
      ))}
    </div>
  );
}

export function Product() {
  return (
    <section id="product" className="scroll-mt-24 py-[84px] pt-0">
      <Container>
        <Reveal className="mb-12 max-w-[680px]">
          <Eyebrow>The product</Eyebrow>
          <h2 className="serif my-3.5 text-[38px]">
            A real conversation, not a quiz.
          </h2>
        </Reveal>

        <FeatureRow
          first
          eyebrow="Real-time voice"
          title="Speak naturally. Get interrupted. Recover."
          body="Sub-second responses, barge-in, and a full transcript of every answer. Speech recognition is chosen so accented English is understood, not penalized."
          bullets={[
            "Behavioral, technical & coding rounds",
            "Live captions & saved transcript",
            "Choose an interviewer persona",
          ]}
          visual={<LanguagesVisual />}
        />

        <FeatureRow
          flip
          eyebrow="Personalized"
          title="Questions built from your CV, the JD & the company."
          body="No generic question bank. A planner agent researches the role and the employer, finds where your experience is thin, and shapes a difficulty curve around it."
          bullets={[
            "CV ↔ JD gap analysis",
            "Company-specific question patterns",
            "Adaptive follow-ups",
          ]}
          visual={<PlanVisual />}
        />

        <FeatureRow
          eyebrow="The loop"
          title="Practice, feedback, study — repeat."
          body="Every interview is scored per competency. Your weak areas flow straight into a document-grounded study coach with flashcards and a voice tutor — then back into the next interview."
          bullets={[
            "Grounded answers with citations",
            "Spaced-repetition flashcards",
            "Mastery tracking across sessions",
          ]}
          visual={<LoopVisual />}
        />
      </Container>
    </section>
  );
}
