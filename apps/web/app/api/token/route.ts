import { NextResponse } from "next/server";
import { z } from "zod";
import type { TokenResponse } from "@deepinterview/shared";
import { getUser } from "@/lib/supabase/server";
import { createInterviewToken } from "@/lib/livekit";
import { isLiveKitConfigured, isSupabaseConfigured } from "@/lib/env";

const BodySchema = z.object({
  session_id: z.string().min(1),
  identity: z.string().min(1).optional(),
});

export async function POST(request: Request) {
  let body: z.infer<typeof BodySchema>;
  try {
    body = BodySchema.parse(await request.json());
  } catch {
    return NextResponse.json(
      { error: "Invalid request body" },
      { status: 400 },
    );
  }

  // Auth: require a user when Supabase is configured; allow a dev identity offline.
  let identity = body.identity;
  let name: string | undefined;

  if (isSupabaseConfigured()) {
    const user = await getUser();
    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
    identity = identity ?? user.id;
    name =
      (user.user_metadata?.name as string | undefined) ??
      user.email ??
      undefined;
  } else {
    identity = identity ?? `dev-${body.session_id}`;
  }

  if (!isLiveKitConfigured()) {
    return NextResponse.json(
      { error: "LiveKit not configured" },
      { status: 501 },
    );
  }

  const { token, url } = await createInterviewToken({
    room: body.session_id,
    identity: identity as string,
    name,
    metadata: { session_id: body.session_id },
  });

  const response: TokenResponse = { token, url, room: body.session_id };
  return NextResponse.json(response);
}
