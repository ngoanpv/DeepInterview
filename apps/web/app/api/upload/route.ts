import { NextResponse } from "next/server";
import { z } from "zod";
import { gateRequest } from "@deepinterview/ee";
import { presignUpload } from "@/lib/r2";
import { isR2Configured } from "@/lib/env";
import { getUser } from "@/lib/supabase/server";

const BodySchema = z.object({
  filename: z.string().min(1),
  content_type: z.string().min(1),
});

export async function POST(request: Request) {
  // Distribution gate (no-op in OSS): presigned uploads cost storage; a
  // distribution with required auth rejects anonymous callers here.
  const user = await getUser();
  const gate = gateRequest({
    pathname: "/api/upload",
    isAuthenticated: Boolean(user),
  });
  if (!gate.allow) {
    return NextResponse.json({ error: "Sign in required" }, { status: 401 });
  }

  let body: z.infer<typeof BodySchema>;
  try {
    body = BodySchema.parse(await request.json());
  } catch {
    return NextResponse.json(
      { error: "Invalid request body" },
      { status: 400 },
    );
  }

  if (!isR2Configured()) {
    return NextResponse.json({ error: "R2 not configured" }, { status: 501 });
  }

  // Namespace the key and strip path separators from the supplied filename.
  const safeName = body.filename.replace(/[/\\]/g, "_");
  const key = `uploads/${Date.now()}-${safeName}`;

  const result = await presignUpload(key, body.content_type);
  return NextResponse.json(result);
}
