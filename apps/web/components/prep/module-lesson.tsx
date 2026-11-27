"use client";

import { useEffect, useState } from "react";
import { Spinner } from "@/components/ui/spinner";
import { askCoach } from "@/lib/coach";
import { useLocale } from "@/lib/i18n/client";
import type { StudyModule } from "@/lib/sample-mastery";

/**
 * The lesson for a started study module, shown right under its card. The coach
 * writes it on open (explanation, worked example, one practice prompt); the
 * request itself stays hidden so the learner sees a lesson, not a chat they
 * never typed. Follow-up questions go to the coach chat beside the plan.
 */
export function ModuleLesson({
  module: m,
  sessionId,
}: {
  module: StudyModule;
  sessionId?: string | null;
}) {
  const locale = useLocale();
  const [lesson, setLesson] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const prompt = `Teach me the study module "${m.title}" (${m.competency}). Why it's in my plan: ${m.rationale} Walk me through it step by step with a worked example, then give me one practice prompt to answer.`;
    askCoach(prompt, locale, sessionId ?? "anonymous")
      .then((res) => {
        if (!cancelled) setLesson(res.answer);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [m.title, m.competency, m.rationale, locale, sessionId]);

  return (
    <div className="border-t border-line px-6 py-5">
      <p className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-faint">
        Lesson
      </p>
      {lesson ? (
        <>
          <p className="mt-2 whitespace-pre-wrap text-[14px] leading-relaxed text-ink-soft">
            {lesson}
          </p>
          <a
            href="#coach"
            className="mt-4 inline-block text-[13px] text-accent"
          >
            Questions? Ask the coach →
          </a>
        </>
      ) : failed ? (
        <p className="mt-2 text-[14px] text-muted">
          I couldn&apos;t reach the coach just now. Reload to try again.
        </p>
      ) : (
        <div className="mt-2 inline-flex items-center gap-2.5 text-[13px] text-muted">
          <Spinner label="Writing your lesson" />
          <span>Writing your lesson…</span>
        </div>
      )}
    </div>
  );
}
