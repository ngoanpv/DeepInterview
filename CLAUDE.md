# CLAUDE.md — DeepInterview

> Entry point for Claude Code. Read this first, then `site/AI-Interviewer-Build-Handoff.md` (the technical spec). Build in the order defined there.

## What we're building
**DeepInterview** — an open-source (AGPLv3), voice-first AI mock-interview platform. It reads a candidate's CV + a job description, researches the target company, runs an adaptive **real-time voice interview** with a stylized video avatar, scores it, then routes the user into a study coach that teaches weak areas — a closed prep ⇄ interview ⇄ feedback loop. **English-first, multilingual (10+ languages).**

## Source-of-truth docs (read in this order)
1. **`site/AI-Interviewer-Build-Handoff.md`** — THE spec. Architecture, prep/live/post phases, recommended stack + OSS alternatives, multi-agent design, the shared `InterviewContext` contract, Veo avatar prompts, **§16 = agent work packages (WP-0…WP-13) with interface contracts, acceptance criteria, and a dependency graph. Start coding from §16.**
2. **`site/Pricing-Business-Model.md`** — pricing tiers, unit economics, plan gating (affects the billing/feature-flag work).
3. **`site/PROJECT-NOTE-Viral-README.md`** — naming, the public `README.md` skeleton to ship, launch checklist.
4. **`site/DeepInterview-Product-Spec.docx`** — human-facing PRD (binary; same content as the handoff — you don't need to parse it).
5. **`site/landing-page.html`** — design reference for the marketing site / visual language (editorial, light, serif display, one indigo accent — match this, not a generic dark gradient).

## Golden rules
1. **Build `packages/shared` (WP-0) FIRST.** It defines the TS + Pydantic contracts every other package imports. Nothing else starts until those types compile and round-trip JSON between web and agent.
2. **Respect the prep / live / post split.** Heavy reasoning runs before the call; the live LiveKit voice loop stays lean (one fast model, precomputed plan, no blocking I/O on the turn path).
3. **English-first, multilingual.** All user-facing strings are i18n'd (EN default). Language is a per-session setting; STT/TTS/voice route by language. Each language is a pluggable "pack."
4. **Cascaded STT→LLM→TTS** (not speech-to-speech) for transcripts + per-component control.
5. **Cost discipline.** Voice has real marginal cost (~$0.50–1.00 per 15-min interview until optimized). Enforce the per-tier interview cap in code; never ship a literally-unlimited voice plan.
6. **Re-verify before wiring billing or pinning models** — prices/model versions in the docs are June-2026 estimates (see handoff §17).
7. **License:** AGPLv3 core; keep any paid/enterprise-only code in a separate `/ee` directory under a commercial license. Don't move core features out of OSS.
8. **Secrets** via env vars only (`.env`, never committed). Provide `.env.example`.

## Target stack (per the handoff — confirm latest at build time)
- **Monorepo:** pnpm + Turborepo.
- **Web (`apps/web`):** Next.js 15.5 (App Router) + React 19 + TypeScript + Tailwind v4 + shadcn/ui. Fork `livekit-examples/agent-starter-react`.
- **Agent (`apps/agent`):** Python 3.11+ (uv), LiveKit Agents; LangGraph for prep/post pipelines. Fork `livekit-examples/agent-starter-python`.
- **Knowledge (`services/lightrag`):** LightRAG + RAG-Anything sidecar (Docker, :9621) for the study coach.
- **Voice:** LiveKit · STT Soniox/Deepgram · TTS Cartesia/ElevenLabs (OSS: faster-whisper / XTTS) · LLM Gemini 3 Flash / GPT-5.1 (OSS: Qwen3).
- **Data:** Supabase (Postgres + Auth + Storage) · Cloudflare R2 (files/recordings).
- **Avatars:** pre-rendered Veo 3.1 idle/speaking loops, crossfaded by agent state (prompts in handoff §8).

## Repo layout to create (WP-0) — pnpm + Turborepo monorepo, with HKUDS/DeepTutor-style conventions
```
deepinterview/
├── .github/                # CI + release workflows, issue templates
├── assets/                 # logo, demo.gif, screenshots (README hero)
├── apps/
│   ├── web/                # Next.js app (fork livekit-examples/agent-starter-react)
│   └── agent/              # Python LiveKit worker + LangGraph prep/post pipelines
├── packages/
│   └── shared/             # TS contracts (mirrored as Pydantic) — BUILD FIRST
├── cli/                    # `deepinterview` CLI + init wizard (writes .env/keys) — adoption lever
├── services/lightrag/      # knowledge sidecar (Docker, :9621)
├── skills/                 # versioned company playbooks + rubrics (Markdown+YAML)
├── packaging/              # pip/npm packaging for the CLI
├── scripts/                # setup / dev / release scripts
├── tests/                  # cross-cutting / e2e tests
├── site/                   # docs site (move the *.md spec files here)
├── ee/                     # enterprise-only (SSO/RBAC/audit) — commercial license
├── docker-compose.yml      # `docker compose up` runs the full stack
├── .env.example  CITATION.cff  .dockerignore
└── turbo.json · pnpm-workspace.yaml · package.json
```
> Backbone = monorepo (co-equal TS web + Python agent + shared cross-language contract). The flat top-level folders (`.github`, `assets`, `cli`, `scripts`, `tests`, `site`, `packaging`, citation) mirror trending HKUDS repos (DeepTutor) for adoption. **The `cli/` init wizard is the key adoption lever** — `deepinterview init` collects provider keys and writes `.env`.

## Build order (phases — see handoff §15/§16)
- **P0:** WP-0 scaffold + shared contracts → a logged-in user joins a LiveKit room and hears a hard-coded agent (EN + one more language).
- **P1:** WP-6 prep pipeline + WP-5 live interviewer + WP-1 setup UI → real CV+JD → personalized 15-min voice interview, transcript saved.
- **P2:** WP-7 scoring + WP-3 report UI + WP-9 avatars.
- **P3:** WP-8 knowledge service + WP-4 Prep Coach UI (the loop).
- **P4:** WP-13 OSS launch assets. **P5:** WP-11 payments/gating. **P6:** `/ee` enterprise.

## Commands (fill in as you scaffold)
```bash
pnpm install
deepinterview init  # CLI wizard: pick providers, set API keys, write .env
pnpm dev            # web + agent locally
docker compose up   # full stack incl. lightrag
pnpm test
pnpm lint && pnpm typecheck
```

## Conventions
- TypeScript strict; Pydantic models mirror `packages/shared` exactly (add a parity check test).
- Keep the live agent prompt small; inject only the compact candidate summary + current question + last turns.
- Tasteful, restrained UI per `landing-page.html` (light, serif display, hairline borders, one accent) — avoid the generic dark-neon-gradient look.
- Conventional commits; small PRs per work package.

## Start here
Read `site/AI-Interviewer-Build-Handoff.md` §16, then implement **WP-0** (monorepo + `packages/shared` contracts + `docker-compose.yml` + `.env.example`). Stop and confirm the contracts compile before moving on.
