import type { ModelAnswer } from "@deepinterview/shared";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Eyebrow } from "@/components/ui/eyebrow";

/**
 * "Better answer" cards. Each ModelAnswer is matched to its question text by
 * `question_id` via the provided lookup map; if a question is unknown we still
 * render the answer under its id. Frosted (paper) panels. Server component.
 */
export function ModelAnswers({
  answers,
  questionText,
}: {
  answers: ModelAnswer[];
  /** question_id -> human question text */
  questionText: Record<string, string>;
}) {
  if (answers.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <Eyebrow>Coaching</Eyebrow>
        <CardTitle className="mt-1">Stronger answers</CardTitle>
        <CardDescription>
          How a top candidate might have framed the moments that cost you
          points.
        </CardDescription>
      </CardHeader>
      <div className="space-y-3 px-6 pb-6">
        {answers.map((a, i) => (
          <div
            key={a.question_id + i}
            className="rounded-[10px] border border-line bg-paper/70 p-4 backdrop-blur-sm"
          >
            <p className="text-[13px] font-medium leading-snug text-ink">
              {questionText[a.question_id] ?? `Question ${a.question_id}`}
            </p>
            <p className="mt-2 border-l-2 border-accent/40 pl-3 text-sm leading-relaxed text-ink-soft">
              {a.answer}
            </p>
          </div>
        ))}
      </div>
    </Card>
  );
}
