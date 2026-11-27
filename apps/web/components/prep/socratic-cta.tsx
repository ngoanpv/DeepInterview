import Link from "next/link";
import { Mic, ArrowRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Eyebrow } from "@/components/ui/eyebrow";
import { RecentSessions } from "@/components/session/recent-sessions";

/**
 * Voice Socratic mode entry point. Reuses the live interview voice loop
 * (LiveKit STT→LLM→TTS) but in a teaching posture: the coach asks leading
 * questions instead of grading. Opens the coach room for the linked interview.
 */
export function SocraticCta({ sessionId }: { sessionId?: string | null }) {
  return (
    <Card className="bg-ink text-white">
      <CardContent className="flex flex-col gap-5 py-6 md:flex-row md:items-center md:justify-between">
        <div className="flex items-start gap-4">
          <span
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-white/10"
            aria-hidden
          >
            <Mic className="h-5 w-5 text-white" />
          </span>
          <div>
            <Eyebrow className="text-white/60">Voice · Socratic mode</Eyebrow>
            <h3 className="mt-1.5 font-serif text-xl text-white">
              Talk it through, out loud
            </h3>
            <p className="mt-1 max-w-xl text-[14px] leading-relaxed text-white/70">
              Instead of grading you, the coach asks leading questions until the
              idea clicks — spoken, hands-free. It reuses the same real-time
              voice pipeline as your interviews, so it feels exactly like the
              room.
            </p>
          </div>
        </div>

        <Link
          href={
            sessionId
              ? `/interview/coach?mode=socratic&session=${encodeURIComponent(sessionId)}`
              : "/setup"
          }
          className="no-underline md:shrink-0"
        >
          <Button
            variant="out"
            className="border-white/30 bg-white/0 text-white hover:border-white hover:bg-white/10"
          >
            {sessionId ? "Start Socratic session" : "Start a mock first"}
            <ArrowRight className="h-4 w-4" aria-hidden />
          </Button>
        </Link>
      </CardContent>
      {!sessionId && (
        <CardContent className="pt-0 pb-6">
          <RecentSessions tone="dark" title="Or coach on a past interview" />
        </CardContent>
      )}
    </Card>
  );
}
