import Link from "next/link";
import { redirect } from "next/navigation";
import { RefreshCw, ArrowRight } from "lucide-react";
import { isSupabaseConfigured } from "@/lib/env";
import { getUser } from "@/lib/supabase/server";
import { Eyebrow } from "@/components/ui/eyebrow";
import { Button } from "@/components/ui/button";
import { LanguageToggle } from "@/components/language-toggle";
import type { StudyModule } from "@deepinterview/shared";
import { SAMPLE_SCORECARD } from "@/lib/sample-scorecard";
import { requestCoachPlan } from "@/lib/api";
import { StudyPlan } from "@/components/prep/study-plan";
import { GroundedChat } from "@/components/prep/grounded-chat";
import { Flashcards } from "@/components/prep/flashcards";
import { MasteryGraphView } from "@/components/prep/mastery-graph";
import { SocraticCta } from "@/components/prep/socratic-cta";

// Reads server-only config (`isSupabaseConfigured()`) and the per-request user;
// must not be statically prerendered.
export const dynamic = "force-dynamic";

/**
 * Prep Coach (WP-4). The closed-loop study surface: it turns the last
 * interview's `weak_competencies` into an ordered study plan, a grounded RAG
 * chat, a spaced-repetition deck, a mastery graph, and a voice Socratic mode —
 * then loops the learner back into a new mock.
 *
 * Server shell: auth-gates only when Supabase is configured (offline it
 * proceeds), then composes the client islands. All data falls back to sample
 * content so the page renders fully with zero env keys.
 */
export default async function PrepPage() {
  // Page-level auth: gate only when Supabase is wired up; offline we proceed.
  if (isSupabaseConfigured()) {
    const user = await getUser();
    if (!user) redirect("/login");
  }

  // Weak areas come from the last interview's scorecard (sample offline).
  const weakAreas = SAMPLE_SCORECARD.weak_competencies;

  // Build the real study plan from the scorecard via the coach agent. Falls back
  // to the StudyPlan component's sample modules if the agent is unreachable.
  let studyModules: StudyModule[] | undefined;
  try {
    const plan = await requestCoachPlan(SAMPLE_SCORECARD);
    if (plan.modules.length > 0) studyModules = plan.modules;
  } catch {
    // Agent down / offline dev — StudyPlan renders its default sample modules.
  }

  return (
    <main className="mx-auto max-w-[1100px] px-6 py-12">
      {/* Header */}
      <header className="flex items-center justify-between">
        <Link href="/" className="no-underline">
          <Eyebrow>DeepInterview</Eyebrow>
        </Link>
        <LanguageToggle />
      </header>

      <div className="mt-6">
        <h1 className="font-serif text-4xl text-ink">Prep Coach</h1>
        <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-muted">
          Your last interview surfaced a few weak areas. Here&apos;s the plan to
          close them — study, drill, talk it through, then run it back.
        </p>
      </div>

      {/* Loop-back banner */}
      <section className="mt-6">
        <div className="flex flex-col items-start gap-4 rounded-card border border-line bg-accent-soft px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <RefreshCw
              className="mt-0.5 h-5 w-5 shrink-0 text-accent"
              aria-hidden
            />
            <div>
              <h2 className="font-serif text-lg text-ink">
                Turn weak areas into your next mock
              </h2>
              <p className="mt-0.5 text-[13.5px] text-muted">
                The fastest way to improve is to study, then test under
                pressure. Loop straight back into a tailored interview.
              </p>
            </div>
          </div>
          <Link href="/setup" className="no-underline sm:shrink-0">
            <Button variant="ink">
              Start a new mock
              <ArrowRight className="h-4 w-4" aria-hidden />
            </Button>
          </Link>
        </div>
      </section>

      {/* Study plan + grounded chat side by side on wide screens */}
      <section className="mt-10 grid gap-8 lg:grid-cols-[1.15fr_1fr]">
        <StudyPlan modules={studyModules} weakAreas={weakAreas} />
        <GroundedChat />
      </section>

      {/* Flashcards + mastery graph */}
      <section className="mt-12 grid gap-10 lg:grid-cols-2">
        <Flashcards />
        <MasteryGraphView />
      </section>

      {/* Voice Socratic mode */}
      <section className="mt-12">
        <SocraticCta />
      </section>
    </main>
  );
}
