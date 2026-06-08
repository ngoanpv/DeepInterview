import { NextResponse } from "next/server";
import { z } from "zod";
import { presignUpload } from "@/lib/r2";
import { isR2Configured } from "@/lib/env";

const BodySchema = z.object({
  filename: z.string().min(1),
  content_type: z.string().min(1),
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

  if (!isR2Configured()) {
    return NextResponse.json({ error: "R2 not configured" }, { status: 501 });
  }

  // Namespace the key and strip path separators from the supplied filename.
  const safeName = body.filename.replace(/[/\\]/g, "_");
  const key = `uploads/${Date.now()}-${safeName}`;

  const result = await presignUpload(key, body.content_type);
  return NextResponse.json(result);
}
