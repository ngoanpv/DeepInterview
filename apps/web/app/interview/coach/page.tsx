import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowRight, Mic } from "lucide-react";
import { buttonClasses } from "@/components/ui/button";
import { Eyebrow } from "@/components/ui/eyebrow";
import { LiveRoom } from "@/components/interview/live-room";
import {
  isLiveKitConfigured,
  isSupabaseConfigured,
  serverEnv,
} from "@/lib/env";
import { createInterviewToken } from "@/lib/livekit";
import { getPersona } from "@/lib/personas";
import { SessionViewSchema, type SessionView } from "@/lib/session";
import { getUser } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

async function loadSession(id: string): Promise<SessionView | null> {
  try {
    const response = await fetch(
      `${serverEnv.agentApiUrl}/api/session/${encodeURIComponent(id)}`,
      { cache: "no-store", signal: AbortSignal.timeout(15_000) },
    );
    if (!response.ok) return null;
    const parsed = SessionViewSchema.safeParse(await response.json());
    return parsed.success ? parsed.data : null;
  } catch {
    return null;
  }
}

function CoachLanding({
  title,
  body,
  sessionId,
}: {
  title: string;
  body: string;
  sessionId?: string;
}) {
  return (
    <main className="mx-auto min-h-screen max-w-3xl px-6 py-16">
      <Link href="/prep" className="no-underline">
        <Eyebrow>DeepInterview · Prep Coach</Eyebrow>
      </Link>
      <section className="mt-10 rounded-card border border-line bg-paper p-8 sm:p-10">
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-accent-soft text-accent">
          <Mic className="h-5 w-5" aria-hidden />
        </span>
        <h1 className="mt-6 font-serif text-4xl text-ink">{title}</h1>
        <p className="mt-3 max-w-xl text-[15px] leading-relaxed text-muted">
          {body}
        </p>
        <div className="mt-7 flex flex-wrap gap-3">
          {sessionId ? (
            <Link
              href={`/report/${encodeURIComponent(sessionId)}`}
              className={buttonClasses()}
            >
              View interview report
            </Link>
          ) : null}
          <Link
            href={sessionId ? "/setup" : "/prep"}
            className={buttonClasses({ variant: "out" })}
          >
            {sessionId ? "Start a new mock" : "Open Prep Coach"}
            <ArrowRight className="h-4 w-4" aria-hidden />
          </Link>
        </div>
      </section>
    </main>
  );
}

export default async function CoachPage({
  searchParams,
}: {
  searchParams: Promise<{
    mode?: string | string[];
    session?: string | string[];
    persona?: string | string[];
  }>;
}) {
  const params = await searchParams;
  const mode = typeof params.mode === "string" ? params.mode : null;
  if (mode && mode !== "socratic") notFound();

  const sessionId =
    typeof params.session === "string" && params.session
      ? params.session
      : null;
  if (!sessionId) {
    return (
      <CoachLanding
        title="Talk it through, out loud"
        body="The Socratic coach asks one focused question at a time and helps you reason through the weak areas from a real interview. Finish a mock and open the coach from your report or Prep Coach page."
      />
    );
  }

  const session = await loadSession(sessionId);
  if (!session || session.session_id !== sessionId) {
    return (
      <CoachLanding
        title="That interview is not ready for coaching"
        body="We could not load its interview context. Check the link, or finish the mock before starting a spoken coaching session."
        sessionId={sessionId}
      />
    );
  }
  if (!session.context) {
    return (
      <CoachLanding
        title="Finish this interview first"
        body="The coach needs the prepared interview context so its questions follow the role and your actual weak areas."
        sessionId={sessionId}
      />
    );
  }

  let identity = `dev-${sessionId}`;
  let name: string | undefined;
  if (isSupabaseConfigured()) {
    const user = await getUser();
    if (user) {
      identity = user.id;
      name =
        (user.user_metadata?.name as string | undefined) ??
        user.email ??
        undefined;
    }
  }

  const personaId =
    typeof params.persona === "string" ? params.persona : undefined;
  const persona = getPersona(personaId);
  let token: string | null = null;
  let url: string | null = null;
  if (isLiveKitConfigured()) {
    const minted = await createInterviewToken({
      room: sessionId,
      identity,
      name,
      metadata: { session_id: sessionId, mode: "socratic" },
      agentName: serverEnv.livekitCoachAgentName,
      dispatchMetadata: { mode: "socratic" },
    });
    token = minted.token;
    url = minted.url;
  }

  return (
    <LiveRoom
      sessionId={sessionId}
      persona={persona}
      token={token}
      url={url}
      mode="coach"
    />
  );
}
