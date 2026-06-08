import type { LanguageReport } from "@deepinterview/shared";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

function Stat({
  label,
  value,
  suffix,
}: {
  label: string;
  value: string;
  suffix?: string;
}) {
  return (
    <div className="rounded-[10px] border border-line bg-paper px-4 py-3">
      <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-faint">
        {label}
      </p>
      <p className="mt-1 font-serif text-2xl text-ink">
        {value}
        {suffix && (
          <span className="ml-0.5 text-base text-faint">{suffix}</span>
        )}
      </p>
    </div>
  );
}

/**
 * Language & delivery report: fluency / clarity on the 0-5 scale, raw filler
 * count, plus the qualitative code-switching and pronunciation notes. Server
 * component.
 */
export function LanguageReportCard({ report }: { report: LanguageReport }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Language & Delivery</CardTitle>
        <CardDescription>{report.summary}</CardDescription>
      </CardHeader>
      <CardContent className="pb-6">
        <div className="grid grid-cols-3 gap-3">
          <Stat
            label="Fluency"
            value={report.fluency_score.toFixed(1)}
            suffix="/5"
          />
          <Stat
            label="Clarity"
            value={report.clarity_score.toFixed(1)}
            suffix="/5"
          />
          <Stat label="Filler words" value={String(report.filler_word_count)} />
        </div>

        <dl className="mt-5 space-y-4">
          <div>
            <dt className="font-mono text-[10px] uppercase tracking-[0.12em] text-faint">
              Code-switching
            </dt>
            <dd className="mt-1 text-sm leading-relaxed text-ink-soft">
              {report.code_switching_notes}
            </dd>
          </div>
          <div>
            <dt className="font-mono text-[10px] uppercase tracking-[0.12em] text-faint">
              Pronunciation
            </dt>
            <dd className="mt-1 text-sm leading-relaxed text-ink-soft">
              {report.pronunciation_notes}
            </dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  );
}
