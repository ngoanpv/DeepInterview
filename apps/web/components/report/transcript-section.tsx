import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export interface TranscriptTurn {
  question_id: string;
  question: string;
  /** Candidate's answer transcript, or null if the question was not reached. */
  transcript: string | null;
}

/**
 * Per-question playback list: the question text and the candidate's answer
 * transcript. The "▶" is a visual affordance only — no real audio yet (recorded
 * playback lands later). Server component.
 */
export function TranscriptSection({ turns }: { turns: TranscriptTurn[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Transcript</CardTitle>
        <CardDescription>
          Replay each turn. Audio playback arrives with recorded sessions.
        </CardDescription>
      </CardHeader>
      <ol className="divide-y divide-line px-6 pb-6">
        {turns.map((t, i) => (
          <li key={t.question_id} className="py-4 first:pt-0">
            <div className="flex items-start gap-3">
              <span
                aria-hidden
                className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-line bg-paper text-[11px] text-accent"
                title="Playback (coming soon)"
              >
                ▶
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-faint">
                  Q{i + 1}
                </p>
                <p className="mt-0.5 text-[14px] font-medium leading-snug text-ink">
                  {t.question}
                </p>
                {t.transcript ? (
                  <p className="mt-2 text-sm leading-relaxed text-ink-soft">
                    {t.transcript}
                  </p>
                ) : (
                  <p className="mt-2 text-sm italic text-faint">
                    Not reached in this session.
                  </p>
                )}
              </div>
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}
