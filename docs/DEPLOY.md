# Deploying DeepInterview

> WP-12 (DevOps / deploy / observability). Implements handoff **§11 (deploy /
> regions / observability)** and the **§12** cost-optimization notes. Goal:
> push-to-deploy web + agent in the **Singapore region**, healthchecks on every
> service, and one dashboard for latency / cost / errors.

Everything here is **provider-agnostic and gated**: with no keys set, the stack
runs fully offline (mock providers, naive RAG) and observability is a clean
no-op. You only wire a provider when you have its DSN/keys.

---

## 1. Why Singapore (`sin1` / SGP)

Primary launch audience is South-East Asia (incl. HCMC). Singapore is the
lowest-latency major cloud region for the region:

- **HCMC ↔ Singapore: < 50 ms** round-trip — well inside the budget for a
  natural-feeling voice turn (STT → LLM → TTS).
- Co-locating the **LiveKit media + the agent worker** in SGP keeps the
  realtime audio path short; the heavy reasoning already ran in prep (handoff
  §2 prep/live/post split), so the live loop just needs low RTT.
- Vercel `sin1`, LiveKit Cloud Singapore, and Supabase `ap-southeast-1` all live
  in the same metro, so cross-service hops stay intra-region.

Region is pinned in:

- `vercel.json` → `"regions": ["sin1"]` (web).
- `deploy.yml` → worker deploy step targets LiveKit Cloud **Singapore** (or
  Render / Fly `sin`).
- Supabase project + R2 bucket: create in / near `ap-southeast-1`.

---

## 2. Topology

| Component        | Where it runs                                   | Port | Health     |
| ---------------- | ----------------------------------------------- | ---- | ---------- |
| **web** (Next)   | Vercel (`sin1`) — or the `web` container        | 3000 | `/api/health` |
| **agent-api**    | Container (Render/Fly `sin`) — FastAPI prep/score | 8000 | `/health`  |
| **agent-worker** | LiveKit Cloud Agents **SGP** (live voice loop)  | —    | LiveKit Cloud |
| **lightrag**     | Container (`sin`) — knowledge sidecar           | 9621 | `/health`  |
| **Supabase**     | Managed (`ap-southeast-1`) — Postgres/Auth/Storage | —  | managed    |
| **R2**           | Cloudflare (global) — CV files + recordings     | —    | managed    |

The agent ships as **one image, two run modes** (`apps/agent/Dockerfile`):
the default `CMD` runs the **API** (`uvicorn …:8000`); overriding the command to
`python -m deepinterview_agent.worker` runs the **worker**. The worker imports
`livekit.agents` at load time, so its image must be built with the `livekit`
extra and given LiveKit/STT/TTS/LLM keys — that's why it is gated behind the
compose `live` profile and a secrets check in CI.

---

## 3. Local full stack

```bash
docker compose up                 # web + agent-api + lightrag (offline-capable)
docker compose --profile live up  # + agent-worker (needs livekit extra + keys)
```

`docker compose config -q` validates the file (also run in CI). Healthchecks use
the in-image runtime (`node` / `python` one-liners) because the slim base images
ship neither `curl` nor `wget`:

- `web` → `GET /api/health`
- `agent-api` → `GET /health`
- `lightrag` → `GET /health`

`web` and `agent-api` `depends_on` `lightrag` being **healthy** before they
start.

### Images

- **web** — `apps/web/Dockerfile`, multi-stage, Next.js **standalone** output
  (`output: 'standalone'` in `next.config.ts`). Build context is the **repo
  root** (pnpm + Turborepo monorepo); `@deepinterview/shared` is built first via
  `pnpm build --filter @deepinterview/web...`. The runner is a slim
  `node apps/web/server.js` with no runtime install.
- **agent** — `apps/agent/Dockerfile`, `python:3.11-slim` + uv. Base
  `uv sync --no-dev` only (no `livekit` / `observability` extras), so the API
  runs on mock providers with zero keys.
- **lightrag** — `services/lightrag/Dockerfile`, naive RAG by default.

---

## 4. Push-to-deploy

`.github/workflows/ci.yml` runs on every push/PR: schema parity, build,
typecheck, lint, JS + Python tests (agent **and** lightrag sidecar), and
`docker compose config -q`.

`.github/workflows/deploy.yml` is the **gated** deploy (manual
`workflow_dispatch` or push to `main`). It is safe by default — each deploy step
is skipped unless its secrets are present (checked **inside** a step via `env:`,
since GitHub does not allow `secrets.*` in a job-level `if:`), and the
destructive CLI commands are commented out until you opt in.

Jobs:

1. **deploy-web** → Vercel (region from `vercel.json` = `sin1`). Needs
   `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`.
2. **build-agent-image** → builds `apps/agent/Dockerfile` and pushes to GHCR.
3. **deploy-agent-worker** → deploys the worker image to **LiveKit Cloud Agents
   (Singapore)** (or Render / Fly `sin`). Needs `LIVEKIT_URL`,
   `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`. Remember the worker variant must be
   built with `--extra livekit`.

### Web on Vercel

`vercel.json` sets `framework: nextjs`, `regions: [sin1]`,
`installCommand: pnpm install --frozen-lockfile`, and
`buildCommand: pnpm build --filter @deepinterview/web...` (the trailing `...`
builds the `@deepinterview/shared` workspace dependency first), with
`outputDirectory: apps/web/.next`.

---

## 5. Environment & secrets

Secrets are env vars only (`.env`, never committed; see `.env.example`). Set the
same keys as **deployment secrets** on each platform:

- **Vercel** (web): `NEXT_PUBLIC_*` (Supabase URL/anon key, app URL), and any
  server keys the web token endpoint needs.
- **LiveKit Cloud** (worker): `LIVEKIT_URL/API_KEY/API_SECRET`, STT/TTS/LLM
  provider + key (Soniox/Deepgram · Cartesia/ElevenLabs · Gemini/OpenAI),
  Supabase service-role key, `LIGHTRAG_URL`.
- **agent-api / lightrag** containers: provider keys as needed; both run offline
  on mocks with none set.

With **no** keys: providers fall back to deterministic mocks, RAG falls back to
the naive backend, and observability is off. The build and tests stay green.

---

## 6. One dashboard: latency · cost · errors

Provider-agnostic and **gated** — no DSN ⇒ no-op, and the SDKs are optional
extras that are **not installed by default** (so the green build never depends
on them):

- **LLM tracing & cost → Langfuse.** Set `LANGFUSE_PUBLIC_KEY` +
  `LANGFUSE_SECRET_KEY`. Traces every prep/post/live LLM call with token counts
  → per-interview cost, latency per node, and prompt/response inspection. This
  is the single pane for the **~$0.50–1.00 / 15-min interview** unit cost
  (handoff §12) and where you watch it trend down as you optimize.
- **Voice / turn latency → LiveKit Cloud metrics.** STT → LLM → TTS turn timing
  and session health, co-located in SGP.
- **Errors → Sentry.** Set `SENTRY_DSN` (server) / `NEXT_PUBLIC_SENTRY_DSN`
  (browser). Web + agent exceptions in one place.

### How the gating works (and why the build stays green)

- **Web** — `apps/web/lib/observability.ts` exposes `initObservability()` +
  `captureError()`; `apps/web/instrumentation.ts` calls it from Next's
  `register()` hook. With no DSN it returns immediately. `@sentry/nextjs` is
  **not** a dependency: the dynamic import uses a **non-literal specifier** so
  neither `tsc` nor `next build` resolves it, and a missing package is caught at
  runtime. To enable: `pnpm add @sentry/nextjs` (in `apps/web`) and set a DSN.
- **Agent** — `apps/agent/src/deepinterview_agent/core/observability.py` exposes
  `init_observability(settings)`, `get_tracer()`, `capture_error()`.
  `sentry-sdk` / `langfuse` are the **`observability`** optional extra (not
  installed by default); imports are lazy + `try/except ImportError`. To enable:
  `uv sync --extra observability` and set the keys, then call
  `init_observability(get_settings())` at process start in `app.py` /
  `worker.py` (intentionally not wired by default to keep the offline path
  dependency-free).

---

## 7. Cost note (handoff §12)

Voice has real marginal cost (~$0.50–1.00 per 15-min interview until optimized).
Keep the live loop lean (one fast model, precomputed plan, no blocking I/O on
the turn path), enforce the per-tier interview cap in code, and watch the
per-interview cost trend in Langfuse. Singapore co-location keeps RTT — and thus
session length and retry cost — down. See `Pricing-Business-Model.md` for the
per-tier caps that must be enforced in billing/feature-flag code.

---

## 8. Checklist

- [ ] Supabase project in `ap-southeast-1`; R2 bucket created.
- [ ] Secrets set on Vercel + LiveKit Cloud (+ container host).
- [ ] `vercel.json` linked to the Vercel project (region `sin1`).
- [ ] Worker image built with `--extra livekit`; deployed to LiveKit Cloud SGP.
- [ ] Healthchecks green: web `/api/health`, agent-api `/health`, lightrag `/health`.
- [ ] (Optional) `SENTRY_DSN` + `LANGFUSE_*` set; uncomment deploy CLI steps.
```
