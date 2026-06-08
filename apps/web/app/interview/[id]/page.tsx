import { redirect } from "next/navigation";
import { isLiveKitConfigured, isSupabaseConfigured } from "@/lib/env";
import { getUser } from "@/lib/supabase/server";
import { createInterviewToken } from "@/lib/livekit";
import { getPersona } from "@/lib/personas";
import { LiveRoom } from "@/components/interview/live-room";

/**
 * Live interview screen (WP-2). Server component.
 *
 * Next 15: `params`/`searchParams` are Promises — await them. Page-level auth:
 * when Supabase is configured and there's no user, redirect to /login; offline
 * (dev) we proceed.
 *
 * Token: minted server-side via `createInterviewToken` behind an
 * `isLiveKitConfigured()` guard (calling the lib directly is simpler than POSTing
 * to our own /api/token and never throws at import). When LiveKit is NOT
 * configured we pass `token=null` so `<LiveRoom>` renders in preview
 * (not-connected) mode — the offline path the build runs with no env keys.
 */
export default async function InterviewPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ persona?: string }>;
}) {
  const { id } = await params;
  const { persona: personaId } = await searchParams;

  let identity = `dev-${id}`;
  let name: string | undefined;

  if (isSupabaseConfigured()) {
    const user = await getUser();
    if (!user) redirect("/login");
    identity = user.id;
    name =
      (user.user_metadata?.name as string | undefined) ??
      user.email ??
      undefined;
  }

  const persona = getPersona(personaId);

  // Mint a token only when LiveKit is configured; otherwise preview mode.
  let token: string | null = null;
  let url: string | null = null;
  if (isLiveKitConfigured()) {
    const minted = await createInterviewToken({
      room: id,
      identity,
      name,
      metadata: { session_id: id },
    });
    token = minted.token;
    url = minted.url;
  }

  return <LiveRoom sessionId={id} persona={persona} token={token} url={url} />;
}
