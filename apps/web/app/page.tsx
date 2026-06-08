import Link from "next/link";
import { Eyebrow } from "@/components/ui/eyebrow";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <main className="mx-auto max-w-[720px] px-6 py-24">
      <Eyebrow>Voice-first AI mock interviews</Eyebrow>

      <h1 className="serif mt-4 text-5xl leading-[1.05] text-ink">
        Rehearse the interview that{" "}
        <span className="text-accent">actually lands the offer</span>.
      </h1>

      <p className="mt-5 max-w-prose text-lg text-ink-soft">
        DeepInterview reads your CV and the job, researches the company, then
        runs an adaptive voice interview — and shows you exactly what to fix.
      </p>

      <div className="mt-8 flex flex-wrap items-center gap-3">
        <Link href="/setup">
          <Button size="lg">Start a mock interview</Button>
        </Link>
        <Link href="/login">
          <Button variant="out" size="lg">
            Sign in
          </Button>
        </Link>
      </div>

      <div className="mt-10 flex flex-wrap gap-2">
        <Badge variant="outline">English-first</Badge>
        <Badge variant="outline">Multilingual</Badge>
        <Badge variant="ok">Offline-safe build</Badge>
      </div>

      <p className="mt-12 text-sm text-muted">
        <Link href="/api/health">/api/health</Link> validates a sample{" "}
        <code className="font-mono text-ink-soft">InterviewContext</code>{" "}
        against the shared Zod contract.
      </p>
    </main>
  );
}
