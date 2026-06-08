# Veo 3.1 avatar render (WP-9)

One-time pipeline that turns the IP-safe prompts in `prompts.ts` into the
pre-rendered idle/speaking loops the web app crossfades in `<AvatarStage>`.

Runtime cost of the avatars is then **~$0/min** — just CDN bytes — instead of
the $0.05–5/min that real-time talking-avatar SaaS charges forever.

## Files

| File | What it is |
| --- | --- |
| `prompts.ts` | Typed `VEO_PROMPTS` map (anime / superhero / recruiter): `reference` + `idle` + `speaking` prompts, verbatim from handoff §8.1. Canonical source. |
| `render.mjs` | Node ESM render CLI. Gated by `GEMINI_API_KEY`; with no key it dry-runs (zero network) and exits 0. |
| `out/` | Where rendered MP4s land locally (created on first real render). |

> `render.mjs` inlines a copy of the prompts because a `.mjs` file can't import
> the `.ts` without a build step. If you edit a prompt, change it in **both**
> `prompts.ts` (canonical) and `render.mjs`.

## The IP rule (load-bearing — read this)

Never render named copyrighted characters (Iron Man / Avengers, named anime
characters, real people). It is infringement for a commercial product **and**
Veo will refuse or silently rewrite the prompt. Use original characters "in the
style of" a genre. Every prompt in `prompts.ts` already carries:

> "original fictional character, not resembling any real person or existing
> franchise; no brand logos."

The superhero prompt additionally states it does **not resemble Iron Man or any
existing franchise hero**. Keep these clauses if you tweak the prompts.

## Workflow (per persona)

1. **Reference still.** Generate one image from the `reference` prompt.
2. **Both loops from that still.** Reuse the reference as the **first frame** of
   the `idle` and `speaking` 8s clips so the two loops match (same outfit, hair,
   lighting, background). Render with **first-frame = last-frame** so each loop
   is seamless. (Veo can't combine first-frame + multi-image reference in one
   request, so the shared first frame is how we keep the two loops consistent.)
3. **Upload.** If R2 is configured, the loops upload to `avatars/<id>-<kind>.mp4`
   and the CLI prints the public URLs.

## Run it

```bash
# Safe dry-run — prints the plan, the prompts, the output paths, the cost,
# and the IP rule. Makes ZERO network calls. Exits 0.
node scripts/veo/render.mjs

# One persona, iteration (fast) model:
node scripts/veo/render.mjs --persona anime

# Final-quality model:
node scripts/veo/render.mjs --persona recruiter --final

# Help:
node scripts/veo/render.mjs --help
```

### Environment

| Var | Required | Purpose |
| --- | --- | --- |
| `GEMINI_API_KEY` | to render | Without it, the CLI dry-runs and exits 0. |
| `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` | optional | Enables upload to Cloudflare R2. |
| `R2_PUBLIC_URL` | optional | Public base used for the printed URLs. |

### Models & cost

- `veo-3.1-fast-generate-preview` — iteration (~$0.10/s → ~$0.80 per 8s loop).
- `veo-3.1-generate-preview` — finals (~$0.40/s → ~$3.20 per 8s loop).

One-time **~$8–40 per character** (reference + idle + speaking, a few takes),
then **~$0/min** at runtime. The whole 3-persona library is a one-time
**~$25–120** and pays for itself within ~10–20 interview-hours vs even the
cheapest real-time avatar SaaS.

> Prices/model ids are June-2026 estimates — confirm on
> ai.google.dev/gemini-api/docs/pricing before spending (handoff §17).

## SynthID watermark

Every Veo output carries an **invisible SynthID watermark**. It's imperceptible
and does not affect playback or compositing — fine to ship. Commercial use is
permitted on paid Gemini tiers.

## Wiring the URLs into the app

After a successful render+upload, the CLI prints lines like:

```
anime idle_url:     "https://<r2-public>/avatars/anime-idle.mp4"
anime speaking_url: "https://<r2-public>/avatars/anime-speaking.mp4"
```

Paste each into the matching persona in **`apps/web/lib/personas.ts`**,
replacing the placeholder `/avatars/<id>-<kind>.mp4` paths (and the
`poster_url`, if you also upload a first-frame JPG). No component changes are
needed — `<AvatarStage>` swaps from its fallback stage to the real videos as
soon as the URLs resolve.
