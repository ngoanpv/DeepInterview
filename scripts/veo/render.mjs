#!/usr/bin/env node
/**
 * render.mjs — DeepInterview avatar render CLI (WP-9).
 *
 * Renders the idle + speaking Veo 3.1 loops for each avatar persona, then
 * (optionally) uploads the MP4s to Cloudflare R2 and prints the resulting URLs
 * to paste into `apps/web/lib/personas.ts`.
 *
 * USAGE
 *   node scripts/veo/render.mjs                 # all personas, fast/iteration model
 *   node scripts/veo/render.mjs --persona anime # one persona
 *   node scripts/veo/render.mjs --final         # final-quality model
 *   node scripts/veo/render.mjs --persona recruiter --final
 *
 * ENV
 *   GEMINI_API_KEY            (required to actually render — otherwise dry-run)
 *   R2_ACCOUNT_ID             (optional — enables upload)
 *   R2_ACCESS_KEY_ID          (optional)
 *   R2_SECRET_ACCESS_KEY      (optional)
 *   R2_BUCKET                 (optional)
 *   R2_PUBLIC_URL             (optional — public base for printed URLs)
 *
 * MODELS
 *   veo-3.1-fast-generate-preview   iteration  (~$0.10/s → ~$0.80 per 8s loop)
 *   veo-3.1-generate-preview        finals     (~$0.40/s → ~$3.20 per 8s loop)
 *
 * COST (one-time, vs $0/min at runtime)
 *   ~$8–40 per character to render reference + idle + speaking, then ~$0/min
 *   forever at runtime (just CDN bytes). A 3-character library is a one-time
 *   ~$25–120 — it pays for itself within ~10–20 interview-hours vs even the
 *   cheapest real-time avatar SaaS.
 *
 * IP RULE (load-bearing)
 *   Every prompt carries: "original fictional character, not resembling any
 *   real person or existing franchise; no brand logos." NEVER render named
 *   copyrighted characters — it's infringement for a commercial product and
 *   Veo will refuse/rewrite it anyway.
 *
 * SAFETY
 *   Gated + offline-safe. With NO GEMINI_API_KEY this script does ZERO network,
 *   prints exactly what it WOULD do, and exits 0. The Gemini SDK is only
 *   lazy-imported when a key is present; otherwise we fall back to raw `fetch`
 *   against the REST endpoint. Nothing is required at import time.
 *
 * WORKFLOW (per persona)
 *   1. Generate ONE reference still from the `reference` prompt.
 *   2. Use that still as the first frame for BOTH loops (idle + speaking) so
 *      they match; render 8s clips, first-frame = last-frame for seamless loop.
 *   3. If R2 is configured, upload the two MP4s and print their public URLs.
 *
 * NOTE: prompts here mirror `scripts/veo/prompts.ts` (the canonical TS source).
 * `.mjs` can't import the `.ts` without a build step, so they are inlined and
 * kept in sync by hand.
 */

import { mkdir, writeFile } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = resolve(__dirname, "out");

const IP_RULE =
  "Original fictional character, not resembling any real person or existing franchise; no brand logos.";
const IP_RULE_SUPERHERO =
  "Original fictional character, not resembling Iron Man or any existing franchise hero, and not resembling any real person or existing franchise; no brand logos.";

/** Mirror of scripts/veo/prompts.ts VEO_PROMPTS (kept in sync by hand). */
const VEO_PROMPTS = {
  anime: {
    reference: `Medium close-up, anime/cel-shaded style. An original anime-style female interviewer in her twenties, neat dark bob with a hair clip, smart-casual blazer, friendly neutral expression, eyeline to camera. Clean pastel-gradient studio background, soft even anime lighting. Static camera. ${IP_RULE}`,
    idle: `Medium close-up, anime/cel-shaded style. An original anime-style female interviewer in her twenties, neat dark bob with a hair clip, smart-casual blazer, friendly neutral expression. Breathes softly, blinks occasionally, slight head tilt. Clean pastel-gradient studio background, soft even anime lighting. No dialogue, quiet ambient room tone. Static camera. First frame matches last frame for a seamless loop. ${IP_RULE}`,
    speaking: `Same anime-style female interviewer — same outfit, hair, lighting, pastel-gradient background, medium close-up. She speaks warmly and animatedly to camera, natural mouth movement, gentle head nods and small hand gestures, engaged expression. Soft even anime lighting. No specific dialogue audio, neutral ambient tone. Static camera. First frame matches last frame for a seamless loop. ${IP_RULE}`,
  },
  superhero: {
    reference: `Medium close-up, cinematic. An original armored superhero in a sleek red-and-gold powered exosuit with a softly glowing chest core and a sculpted helmet (open, confident human face visible), eyeline to camera. Dark neutral studio background, cool-blue rim lighting. Static camera. ${IP_RULE_SUPERHERO}`,
    idle: `Medium close-up, cinematic. An original armored superhero in a sleek red-and-gold powered exosuit with a softly glowing chest core and a sculpted helmet (open, confident human face visible). Subtle breathing, occasional blink, faint pulsing suit glow. Dark neutral studio background, cool-blue rim lighting. Calm and heroic. No dialogue, low ambient hum. Static camera. First frame matches last frame for a seamless loop. ${IP_RULE_SUPERHERO}`,
    speaking: `Same original red-and-gold armored superhero, helmet open, same dark studio background and cool-blue rim lighting, medium close-up. Speaks confidently to camera, natural mouth movement, assured nods and a subtle hand gesture, chest core glowing steadily. Cinematic dramatic lighting. No specific dialogue audio, low ambient hum. Static camera. First frame matches last frame for a seamless loop. ${IP_RULE_SUPERHERO}`,
  },
  recruiter: {
    reference: `Medium close-up, photorealistic. A fictional professional male recruiter, late thirties, short tidy hair, light beard, navy blazer over white shirt, warm approachable expression, eyeline to camera, not resembling any real person. Clean light-grey office-studio background with soft bokeh, soft three-point lighting, warm key from left. Static camera. ${IP_RULE}`,
    idle: `Medium close-up, photorealistic. A fictional professional male recruiter, late thirties, short tidy hair, light beard, navy blazer over white shirt, warm approachable expression, not resembling any real person. Subtle breathing, natural blinking, slight head movement. Clean light-grey office-studio background with soft bokeh, soft three-point lighting, warm key from left. No dialogue, quiet office ambience. Static camera. First frame matches last frame for a seamless loop. ${IP_RULE}`,
    speaking: `Same fictional male recruiter — same blazer, hair, background, soft three-point lighting, medium close-up. Speaks in a warm professional manner to camera, natural lip movement, occasional reassuring nods and a small open-hand gesture, attentive expression. No specific dialogue audio, quiet office ambience. Static camera. First frame matches last frame for a seamless loop. ${IP_RULE}`,
  },
};

const PERSONA_IDS = ["anime", "superhero", "recruiter"];

const MODEL_FAST = "veo-3.1-fast-generate-preview";
const MODEL_FINAL = "veo-3.1-generate-preview";

// ---------------------------------------------------------------------------
// arg parsing
// ---------------------------------------------------------------------------

function parseArgs(argv) {
  const args = { persona: null, final: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--final") args.final = true;
    else if (a === "--persona") args.persona = argv[++i];
    else if (a.startsWith("--persona=")) args.persona = a.slice("--persona=".length);
    else if (a === "-h" || a === "--help") args.help = true;
  }
  return args;
}

function printHelp() {
  console.log(
    [
      "DeepInterview avatar render CLI (WP-9)",
      "",
      "Usage:",
      "  node scripts/veo/render.mjs [--persona <id>] [--final]",
      "",
      "Flags:",
      "  --persona <id>   anime | superhero | recruiter (default: all)",
      "  --final          use the final-quality model (default: fast/iteration)",
      "  -h, --help       show this help",
      "",
      "Set GEMINI_API_KEY to actually render. Without it this is a safe dry-run.",
    ].join("\n"),
  );
}

// ---------------------------------------------------------------------------
// env helpers
// ---------------------------------------------------------------------------

function r2Config() {
  const {
    R2_ACCOUNT_ID,
    R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY,
    R2_BUCKET,
    R2_PUBLIC_URL,
  } = process.env;
  if (
    R2_ACCOUNT_ID &&
    R2_ACCESS_KEY_ID &&
    R2_SECRET_ACCESS_KEY &&
    R2_BUCKET
  ) {
    return {
      accountId: R2_ACCOUNT_ID,
      accessKeyId: R2_ACCESS_KEY_ID,
      secretAccessKey: R2_SECRET_ACCESS_KEY,
      bucket: R2_BUCKET,
      publicUrl: R2_PUBLIC_URL || null,
    };
  }
  return null;
}

// ---------------------------------------------------------------------------
// dry-run (no GEMINI_API_KEY): explain, do ZERO network, exit 0
// ---------------------------------------------------------------------------

function dryRun(personas, model) {
  const r2 = r2Config();
  console.log("");
  console.log("DeepInterview · Veo 3.1 avatar render (DRY RUN)");
  console.log("================================================");
  console.log("");
  console.log("GEMINI_API_KEY is not set — no network calls will be made.");
  console.log("Set it to render for real. This run only explains the plan.\n");
  console.log(`Model:        ${model}`);
  console.log(`Output dir:   ${OUT_DIR}`);
  console.log(`R2 upload:    ${r2 ? "configured ✓ (would upload MP4s)" : "not configured (would write local MP4s only)"}`);
  console.log("");
  console.log("IP rule (load-bearing, in every prompt):");
  console.log(`  "${IP_RULE}"`);
  console.log("");
  console.log("Cost: one-time ~$8–40 per character to render, then ~$0/min at");
  console.log("runtime (CDN bytes only). Whole 3-persona library ≈ $25–120 once.\n");

  for (const id of personas) {
    const p = VEO_PROMPTS[id];
    console.log(`── ${id} ───────────────────────────────────────────`);
    console.log("  Step 1 · reference still (first frame for both loops):");
    console.log(`    ${p.reference}`);
    console.log("  Step 2 · idle loop  → " + outPath(id, "idle"));
    console.log(`    ${p.idle}`);
    console.log("  Step 3 · speaking loop → " + outPath(id, "speaking"));
    console.log(`    ${p.speaking}`);
    if (r2) {
      console.log("  Step 4 · upload to R2, then paste these into apps/web/lib/personas.ts:");
      console.log(`    idle_url:     ${r2PublicUrl(r2, id, "idle")}`);
      console.log(`    speaking_url: ${r2PublicUrl(r2, id, "speaking")}`);
    } else {
      console.log("  Step 4 · (R2 not configured — would skip upload; wire local files manually)");
    }
    console.log("");
  }

  console.log("Done (dry run). No network calls were made. Set GEMINI_API_KEY to render.");
}

function outPath(id, kind) {
  return resolve(OUT_DIR, `${id}-${kind}.mp4`);
}

function r2Key(id, kind) {
  return `avatars/${id}-${kind}.mp4`;
}

function r2PublicUrl(r2, id, kind) {
  const base = r2.publicUrl
    ? r2.publicUrl.replace(/\/$/, "")
    : `https://${r2.accountId}.r2.cloudflarestorage.com/${r2.bucket}`;
  return `${base}/${r2Key(id, kind)}`;
}

// ---------------------------------------------------------------------------
// live render (GEMINI_API_KEY present). Lazy SDK import; REST fallback.
// ---------------------------------------------------------------------------

async function liveRender(personas, model, apiKey) {
  await mkdir(OUT_DIR, { recursive: true });

  // Prefer the official SDK if it's installed; otherwise use raw fetch.
  let genai = null;
  try {
    genai = await import("@google/genai");
    console.log("Using @google/genai SDK.");
  } catch {
    console.log("@google/genai not installed — using raw REST via fetch.");
  }

  const r2 = r2Config();
  const printed = [];

  for (const id of personas) {
    const p = VEO_PROMPTS[id];
    console.log(`\n── ${id} ─────────────────────────────────────────`);

    // Step 1: reference still — first frame shared by both loops.
    console.log("  Generating reference still…");
    const referenceImage = genai
      ? await sdkGenerateImage(genai, apiKey, p.reference)
      : await restGenerateImage(apiKey, p.reference);

    // Steps 2 & 3: idle + speaking loops from the same first frame.
    for (const kind of ["idle", "speaking"]) {
      console.log(`  Rendering ${kind} loop (8s, seamless)…`);
      const mp4 = genai
        ? await sdkGenerateVideo(genai, apiKey, model, p[kind], referenceImage)
        : await restGenerateVideo(apiKey, model, p[kind], referenceImage);

      const localPath = outPath(id, kind);
      await writeFile(localPath, mp4);
      console.log(`    wrote ${localPath}`);

      // Step 4: optional R2 upload.
      if (r2) {
        await uploadToR2(r2, r2Key(id, kind), mp4);
        const url = r2PublicUrl(r2, id, kind);
        printed.push({ id, kind, url });
        console.log(`    uploaded → ${url}`);
      }
    }
  }

  if (printed.length) {
    console.log("\nPaste these into apps/web/lib/personas.ts:");
    for (const id of personas) {
      const idle = printed.find((x) => x.id === id && x.kind === "idle");
      const speaking = printed.find((x) => x.id === id && x.kind === "speaking");
      if (idle) console.log(`  ${id} idle_url:     "${idle.url}"`);
      if (speaking) console.log(`  ${id} speaking_url: "${speaking.url}"`);
    }
  } else if (!r2) {
    console.log("\nR2 not configured — MP4s are local only. Upload them and");
    console.log("paste the public URLs into apps/web/lib/personas.ts.");
  }

  console.log("\nNote: every Veo output carries an invisible SynthID watermark (fine).");
  console.log("Done.");
}

// --- SDK paths (best-effort; shapes may need adjusting to the installed SDK) ---

async function sdkGenerateImage(genai, apiKey, prompt) {
  const { GoogleGenAI } = genai;
  const ai = new GoogleGenAI({ apiKey });
  const res = await ai.models.generateImages({
    model: "imagen-3.0-generate-002",
    prompt,
    config: { numberOfImages: 1 },
  });
  const img = res?.generatedImages?.[0]?.image;
  if (!img) throw new Error("No reference image returned by SDK.");
  return img; // pass through as first-frame reference for the video call
}

async function sdkGenerateVideo(genai, apiKey, model, prompt, referenceImage) {
  const { GoogleGenAI } = genai;
  const ai = new GoogleGenAI({ apiKey });
  let op = await ai.models.generateVideos({
    model,
    prompt,
    image: referenceImage,
    config: { numberOfVideos: 1, durationSeconds: 8 },
  });
  while (!op?.done) {
    await sleep(10_000);
    op = await ai.operations.getVideosOperation({ operation: op });
  }
  const file = op?.response?.generatedVideos?.[0]?.video;
  if (!file) throw new Error("No video returned by SDK.");
  const blob = await ai.files.download({ file });
  return Buffer.from(await blob.arrayBuffer());
}

// --- REST fallback (raw fetch against the Gemini API) ---

const REST_BASE = "https://generativelanguage.googleapis.com/v1beta";

async function restGenerateImage(apiKey, prompt) {
  // Imagen predict endpoint returns base64 bytes.
  const res = await fetch(
    `${REST_BASE}/models/imagen-3.0-generate-002:predict?key=${apiKey}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        instances: [{ prompt }],
        parameters: { sampleCount: 1 },
      }),
    },
  );
  if (!res.ok) throw new Error(`Imagen REST error ${res.status}: ${await res.text()}`);
  const json = await res.json();
  const b64 = json?.predictions?.[0]?.bytesBase64Encoded;
  if (!b64) throw new Error("No reference image bytes returned by REST.");
  return { imageBytes: b64, mimeType: "image/png" };
}

async function restGenerateVideo(apiKey, model, prompt, referenceImage) {
  // Long-running operation: start, then poll until done, then download.
  const start = await fetch(
    `${REST_BASE}/models/${model}:predictLongRunning?key=${apiKey}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        instances: [
          {
            prompt,
            image: {
              bytesBase64Encoded: referenceImage.imageBytes,
              mimeType: referenceImage.mimeType,
            },
          },
        ],
        parameters: { durationSeconds: 8, sampleCount: 1 },
      }),
    },
  );
  if (!start.ok)
    throw new Error(`Veo REST start error ${start.status}: ${await start.text()}`);
  let op = await start.json();

  while (!op?.done) {
    await sleep(10_000);
    const poll = await fetch(`${REST_BASE}/${op.name}?key=${apiKey}`);
    if (!poll.ok)
      throw new Error(`Veo REST poll error ${poll.status}: ${await poll.text()}`);
    op = await poll.json();
  }

  const uri =
    op?.response?.generateVideoResponse?.generatedSamples?.[0]?.video?.uri;
  if (!uri) throw new Error("No video URI in REST response.");
  const dl = await fetch(`${uri}&key=${apiKey}`);
  if (!dl.ok) throw new Error(`Veo download error ${dl.status}`);
  return Buffer.from(await dl.arrayBuffer());
}

// --- R2 upload (lazy SDK import; only when configured) ---

async function uploadToR2(r2, key, bytes) {
  let s3mod;
  try {
    s3mod = await import("@aws-sdk/client-s3");
  } catch {
    throw new Error(
      "R2 is configured but @aws-sdk/client-s3 is not installed; cannot upload.",
    );
  }
  const { S3Client, PutObjectCommand } = s3mod;
  const client = new S3Client({
    region: "auto",
    endpoint: `https://${r2.accountId}.r2.cloudflarestorage.com`,
    credentials: {
      accessKeyId: r2.accessKeyId,
      secretAccessKey: r2.secretAccessKey,
    },
  });
  await client.send(
    new PutObjectCommand({
      Bucket: r2.bucket,
      Key: key,
      Body: bytes,
      ContentType: "video/mp4",
    }),
  );
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    printHelp();
    process.exit(0);
  }

  let personas = PERSONA_IDS;
  if (args.persona) {
    if (!PERSONA_IDS.includes(args.persona)) {
      console.error(
        `Unknown persona "${args.persona}". Valid: ${PERSONA_IDS.join(", ")}.`,
      );
      process.exit(1);
    }
    personas = [args.persona];
  }

  const model = args.final ? MODEL_FINAL : MODEL_FAST;
  const apiKey = process.env.GEMINI_API_KEY;

  if (!apiKey) {
    // Offline-safe: explain and exit 0 with ZERO network.
    dryRun(personas, model);
    process.exit(0);
  }

  await liveRender(personas, model, apiKey);
}

main().catch((err) => {
  console.error("\nrender.mjs failed:", err?.message || err);
  process.exit(1);
});
