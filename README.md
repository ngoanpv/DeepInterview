<div align="center">

<img src="assets/logo.svg" width="132" alt="DeepInterview" />

# DeepInterview: Voice-First, Multilingual AI Mock Interviewer

### Practice the interview out loud. Then pass the real one. · English-first · Open source

[![License: AGPL v3](https://img.shields.io/badge/License-AGPLv3-4338CA.svg)](LICENSE)
[![Build](https://img.shields.io/github/actions/workflow/status/your-org/deepinterview/ci.yml?branch=main&label=build)](https://github.com/your-org/deepinterview/actions)
[![Release](https://img.shields.io/github/v/release/your-org/deepinterview?include_prereleases&label=release&color=4338CA)](https://github.com/your-org/deepinterview/releases)
[![Stars](https://img.shields.io/github/stars/your-org/deepinterview?style=social)](https://github.com/your-org/deepinterview/stargazers)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-4338CA.svg)](apps/agent)
[![pnpm](https://img.shields.io/badge/pnpm-workspace-4338CA.svg)](pnpm-workspace.yaml)
[![Discord](https://img.shields.io/badge/Discord-join-5865F2?logo=discord&logoColor=white)](#-community)

**🇺🇸 English** · [🇻🇳 Tiếng Việt](README.vi.md)

[Features](#-features) · [Quickstart](#-quickstart) · [Architecture](#️-architecture) · [Roadmap](#️-roadmap) · [Community](#-community) · [Contributing](#-contributing)

</div>

---

<!-- HERO: a 15–40s GIF of a real voice interview + the scorecard. -->
<!-- The file is not recorded yet — see assets/README.md (it's the top launch-checklist item). -->
![DeepInterview demo](assets/demo.gif)

> **🚧 demo.gif is a placeholder.** The hero demo is the launch-critical asset and has not been recorded yet — see [`assets/README.md`](assets/README.md).

> **Upload your CV and a job description. Talk to an AI interviewer. Get scored — and coached on exactly what you missed.** Voice-first, English-first, and multilingual by design.

DeepInterview closes the **prep ⇄ interview ⇄ feedback** loop: heavy reasoning runs *before* the call (read your CV + the JD, research the company, build an adaptive question plan), a lean real-time voice loop runs the interview, then strong models score it and route you into a study coach for your weak areas.

> **Honest status:** this is an **early open build**. The contracts, prep/live/post pipelines, web screens, and CLI are implemented and **run offline with mock adapters** (no API keys, tests green). Real-time voice, web research, and video avatars need provider keys, and `docker compose up` becomes the true full-stack one-liner as DevOps (WP-12) lands. We mark what's done honestly in the [Roadmap](#️-roadmap).

## 📰 News

> - **[2026.06]** 🧱 **Early build is up.** Cross-language `InterviewContext` contract (TS ↔ Pydantic) round-trips; prep/live/post pipelines and all web screens run **offline with mock adapters**. Pre-launch.
> - **[next]** 🎙️ First end-to-end voice interview on real providers (STT→LLM→TTS on LiveKit) + the hero demo GIF.
> - **[next]** 🌐 More language packs and the hosted live demo.

_(Changelog is intentionally pre-launch and honest — no "1,000 stars" or shipped-feature claims until they're true.)_

## 📦 Releases

No tagged release yet — DeepInterview is pre-`v0.1`. Watch [Releases](https://github.com/your-org/deepinterview/releases) and the News section above. Citation metadata lives in [`CITATION.cff`](CITATION.cff).

## ✨ Features

- **🎙️ Real-time voice interview** — cascaded **STT → LLM → TTS** on LiveKit (not speech-to-speech), so you get a full transcript, per-component control, and predictable cost. Barge-in and seeded follow-ups keep it conversational.
- **🌐 English-first & multilingual** — every user-facing string is i18n'd (EN default, VI shipped); language is a per-session setting and STT/TTS/voice route by language. Each language is a pluggable "pack."
- **🧠 Personalized prep** — a LangGraph pipeline reads your CV + the JD, researches the target company, diffs the gap, and a **Question Planner** precomputes the plan, difficulty curve, rubrics, and seeded follow-ups — so the live loop stays fast. Uploaded **CV documents (PDF/DOCX) are parsed to text server-side with [Microsoft markitdown](https://github.com/microsoft/markitdown), with a Gemini multimodal fallback for scanned/image PDFs** — so a résumé file becomes a real candidate profile instead of garbled characters.
- **📊 Scored feedback** — a rubric-based evaluator + language coach write a per-competency `ScoreCard` with strengths, gaps, model answers, and next steps that map straight back to the questions you were asked.
- **📚 Prep Coach** *(in progress)* — turns your gaps into a grounded, cited study loop backed by a LightRAG knowledge sidecar.
- **🎭 Cost-smart avatars** — pre-rendered **Veo 3.1** idle/speaking video loops crossfaded by agent state. Original anime / superhero / recruiter personas (no named IP), so runtime cost is **CDN-only — no per-minute avatar fees**.
- **🔌 Provider-agnostic & self-hostable** — a clean adapter layer (LLM / search / embeddings, with a **mock adapter** for offline dev). Bring your own keys (Soniox/Deepgram, Cartesia/ElevenLabs, Gemini/GPT, or OSS faster-whisper / XTTS / Qwen3).
- **🔓 Open source (AGPLv3)** — self-host the whole thing. Any paid/enterprise-only code is isolated under [`ee/`](ee/README.md).

## 🚀 Quickstart

**Requirements:** Node **20+** (22 recommended — see [`.nvmrc`](.nvmrc)) · pnpm 11 · Python 3.11+ with [uv](https://docs.astral.sh/uv/) (for the agent) · Docker (for the full stack).

### 1. Offline path (verified — no API keys needed)

This is what's tested in CI today. It builds the contracts, runs the test suites, and exercises the prep/live/post pipelines against **mock adapters** — no provider keys required.

```bash
git clone https://github.com/your-org/deepinterview.git
cd deepinterview

pnpm install          # install the JS/TS workspace
pnpm build            # build packages/shared (contracts) + cli + web
pnpm test             # TS + Pydantic parity + pipeline tests (offline, mock adapters)

pnpm deepinterview init   # scaffold .env from .env.example (fill in keys later)
```

> `pnpm build` must run before `pnpm deepinterview init` — the CLI is built into `cli/dist/`.
> For the Python agent: `uv --directory apps/agent sync` then `uv --directory apps/agent run pytest`.

### 2. Full-stack path (target — `docker compose up`)

```bash
cp .env.example .env      # then fill in your provider keys
docker compose up         # web (:3000) + agent worker + lightrag (:9621)
```

> **Status:** the compose file validates (`docker compose config`) and wires all three services. Real images, healthchecks, and the "open http://localhost:3000 and talk to it" experience are being finished in **DevOps (WP-12)**. Until then, prefer the offline path above for development.

<details><summary>Configuring providers & adding a language pack</summary>

- **Keys** live in `.env` only (never committed). See [`.env.example`](.env.example) for the full list (LiveKit, Supabase, R2, STT/TTS/LLM, Tavily/Exa, payments, observability).
- **Provider choice** is per-component: set `STT_PROVIDER`, `TTS_PROVIDER`, `LLM_PROVIDER` and the matching key. With no keys set, the agent falls back to **mock adapters** so everything still runs offline.
- **Languages** are pluggable packs. UI strings live in `apps/web/lib/i18n/messages/` (EN + VI shipped); the question plan carries `text_en` / `text_vi` and a `language_mode`.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full dev setup and the provider-adapter pattern.

</details>

## 🏗️ Architecture

The spine of the system is a **prep / live / post** split (strong async models before and after the call; one lean fast model on the live turn path). All three phases thread a single shared `InterviewContext` "blackboard" — written in prep, read+appended in live, read in post.

```
┌──────────── PREP (async · parallel · STRONG models · web tools) ────────────┐
│  CV ─┐                                                                        │
│  JD ─┼─►  LangGraph StateGraph (Orchestrator)         [WP-6]                  │
│ comp ┘     ├─ fan-out ─► [CV Analysis] [JD Analysis] [Company Research·web]   │
│            └─ join ────► [Gap/Matching] ─► [Question Planner ★]               │
└───────────────────────────────────┬──────────────────────────────────────────┘
                                     ▼
                 ┌──────── InterviewContext (shared blackboard) ───────┐
                 │ candidate · job · company · gap · QUESTION_PLAN      │  [WP-0]
                 │ persisted in Postgres; loaded into LiveKit userdata  │
                 └───────────────────────────┬─────────────────────────┘
                                             ▼
┌──────────── LIVE (realtime <800ms · ONE fast model · LiveKit) ──────────────┐
│  AgentSession[InterviewContext]                       [WP-5]                  │
│   STT ─► [Interviewer Agent] ──reads plan, asks, light follow-up──► TTS       │
│                 ├─► [Coding-round Agent]   (handoff, own model/voice)         │
│                 └─► [Behavioral/STAR Agent]                                   │
│   <AvatarStage> crossfades Veo idle/speaking loops by agent state  [WP-9]     │
│   Director runs in BACKGROUND — never blocks a turn                           │
└───────────────────────────────────┬──────────────────────────────────────────┘
                          transcript + answers appended
                                     ▼
┌──────────── POST (async · STRONG/reasoning models · no latency budget) ─────┐
│  [Evaluator/Scorer] ─► [Language Coach EN/VI] ─► [Report Generator]  [WP-7]   │
│         writes per-competency ScoreCard ─► report screen            [WP-3]    │
│  Prep Coach re-plan (weak competencies) ◄── closes the loop         [WP-4/8]  │
│  Skill Distiller proposes playbook/rubric deltas → review queue     [WP-10]   │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Module boundaries:** `apps/web` owns UI/auth/upload/token and knows nothing about LLM/STT/TTS · `apps/agent` owns the voice loop + prep/post pipelines + avatar render util · `services/lightrag` owns the knowledge base · `cli/` owns first-run setup · **`packages/shared` is the cross-language contract** (TS source of truth, mirrored as Pydantic). See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and the full spec in [`site/AI-Interviewer-Build-Handoff.md`](site/AI-Interviewer-Build-Handoff.md).

## 📸 Screenshots

> Placeholders — see [`assets/README.md`](assets/README.md). The screens exist (`/setup`, `/interview/[id]`, `/report/[id]`); polished captures land with the demo.

| Setup | Live interview | Report |
|---|---|---|
| ![setup](assets/screenshot-setup.png) | ![interview](assets/screenshot-interview.png) | ![report](assets/screenshot-report.png) |

## 🗺️ Roadmap

The build is organized into **13 work packages (WP-0…WP-13)** across phases **P0–P6**. Phases P0–P3 are implemented and offline-verified with mock adapters; P4–P6 are scaffolded.

| Phase | Work packages | What it delivers | Status |
|---|---|---|---|
| **P0** | WP-0 | Monorepo + shared TS↔Pydantic contracts + CLI scaffold + `docker-compose` | ✅ Built · offline-verified |
| **P1** | WP-6, WP-5, WP-1 | Prep pipeline · live voice interviewer · setup/onboarding UI | ✅ Built · offline-verified |
| **P2** | WP-7, WP-3, WP-9 | Scoring pipeline · report screen · Veo avatar system | ✅ Built · offline-verified |
| **P3** | WP-8, WP-4 | Knowledge service (LightRAG) · Prep Coach UI (the loop) | ✅ Built · offline-verified |
| **P4** | WP-13 | OSS launch assets (this README, docs, good-first-issues) | 🟡 In progress |
| **P5** | WP-11, WP-10 | Payments + plan gating · skill library + distiller | 🟡 Scaffolded |
| **P6** | WP-12, `ee/` | DevOps/deploy/observability · enterprise (SSO/RBAC/audit) | 🟡 Scaffolded |

> "Offline-verified" means the pipeline runs end-to-end against mock adapters with tests green — **real-time voice on live providers and a hosted demo are the next milestone**, not a current claim.

**Find it useful? [Give us a ⭐](https://github.com/your-org/deepinterview)** — star velocity is what gets a project discovered, and it genuinely helps.

## 🌐 Community

- 💬 **Discord** — join the build-in-public chat _(invite link TBD — opens at launch)_.
- 🗣️ **[GitHub Discussions](https://github.com/your-org/deepinterview/discussions)** — questions, ideas, language-pack requests.
- 🐛 **[Issues](https://github.com/your-org/deepinterview/issues)** — bugs & features (templates provided).

Built in the open. We respond to issues — ghosting contributors is the #1 cause of OSS death, and we don't intend to.

## 🤝 Contributing

We'd love your help — especially **language packs**, **provider adapters**, and **accessibility**. Start with:

- 📖 [CONTRIBUTING.md](CONTRIBUTING.md) — dev setup, the monorepo map, the work-package model, the provider-adapter (mock-first) pattern, and how to run **offline with no keys**.
- 🌱 [Good first issues](docs/GOOD_FIRST_ISSUES.md) — concrete, scoped tasks drawn from real gaps.
- 📜 [Code of Conduct](CODE_OF_CONDUCT.md) · 🔒 [Security policy](SECURITY.md).

<!-- Contributor mosaic — populates after the repo is public (contrib.rocks reads the public contributor list). -->
[![Contributors](https://contrib.rocks/image?repo=your-org/deepinterview)](https://github.com/your-org/deepinterview/graphs/contributors)

> _The mosaic above renders once the repo is public and has contributors._

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=your-org/deepinterview&type=Date)](https://star-history.com/#your-org/deepinterview&Date)

## 📖 Citation

If DeepInterview helps your work, please cite it. Full metadata is in [`CITATION.cff`](CITATION.cff).

```bibtex
@software{deepinterview2026,
  title  = {DeepInterview: Voice-First, Multilingual AI Mock Interviewer},
  author = {The DeepInterview contributors},
  year   = {2026},
  license = {AGPL-3.0-only},
  url    = {https://github.com/your-org/deepinterview}
}
```

---

<div align="center">

**License:** [AGPL-3.0-only](LICENSE) for the core · commercial terms for [`ee/`](ee/README.md). · Built in the open 🌍

[⬆ back to top](#deepinterview-voice-first-multilingual-ai-mock-interviewer)

</div>
