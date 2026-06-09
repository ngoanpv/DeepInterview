# Good first issues

A curated list of small, self-contained tasks grounded in real gaps in the
current codebase. Each is sized for a first contribution: clear scope, named
files, and a concrete acceptance bar. The project is **mock-first and offline** —
you can build and test every one of these with **no API keys**.

New here? Read [`CONTRIBUTING.md`](../CONTRIBUTING.md) and
[`docs/ARCHITECTURE.md`](ARCHITECTURE.md) first. Comment on the issue (or open
one) before you start so we can avoid duplicate work. Conventional Commits,
please.

Difficulty: 🟢 easy · 🟡 moderate · 🟠 involved.

---

### 1. 🟢 Wire up the Vietnamese (`vi`) UI message pack

**Problem.** `apps/web/lib/i18n/index.ts` maps `vi: en` — Vietnamese currently
falls back to English even though `apps/web/lib/i18n/messages/vi.ts` exists. The
app is meant to be English-first *and* truly multilingual.

**Files.** `apps/web/lib/i18n/index.ts`, `apps/web/lib/i18n/messages/vi.ts`,
`apps/web/lib/i18n/messages/en.ts` (as the key reference).

**Acceptance.** `index.ts` resolves `vi` to the real `vi` dictionary; `vi.ts`
implements the same `Messages` shape as `en.ts` (every key present, types
compile); missing keys still fall back safely via `t()`. Switching the language
toggle to Vietnamese shows translated strings, not English. `pnpm typecheck`
green.

---

### 2. 🟡 Add a Deepgram STT adapter behind a new `STTAdapter` interface

**Problem.** `core/adapters/base.py` defines `Protocol`s for LLM, Search, and
Embeddings, but there is **no STT adapter interface** yet — speech-to-text lives
implicitly in the live path. To keep STT swappable (golden rule: cascaded
STT→LLM→TTS, provider-agnostic), introduce an `STTAdapter` `Protocol` and a first
real implementation.

**Files.** `apps/agent/src/deepinterview_agent/core/adapters/base.py` (add
`STTAdapter`), a new `core/adapters/deepgram.py` (real impl, lazy SDK import),
`core/adapters/mock.py` (deterministic mock STT), and `tests/test_adapters.py`.

**Acceptance.** New `STTAdapter` Protocol with a documented transcribe method; a
mock implementation used by default (offline, no key); the Deepgram impl is only
constructed when its env var is set and imports its SDK lazily (module imports
clean with no key). `uv --directory apps/agent run pytest` green, including a new
adapter test.

---

### 3. 🟡 Replace the recharts radar with a custom SVG competency chart

**Problem.** `apps/web/components/report/competency-chart.tsx` pulls in the whole
`recharts` library just to draw one radar. A hand-rolled SVG removes a heavy
client dependency and lets the chart match the editorial visual language
(hairline borders, one indigo accent).

**Files.** `apps/web/components/report/competency-chart.tsx` (rewrite),
`apps/web/package.json` (drop `recharts` if nothing else uses it — grep first).

**Acceptance.** The radar renders from the same `CompetencyScore[]` prop with no
visual regression on the report screen; `recharts` import removed; respects
reduced-motion; `pnpm build` + `pnpm typecheck` green. Include a before/after
screenshot in the PR.

---

### 4. 🟠 Accessibility pass on the live interview screen

**Problem.** The live interview UI (`apps/web/components/interview/*`) is the
most interaction-heavy screen and needs a focused a11y review: focus management
when the room connects, an accessible name on the mic/control buttons, a live
region for transcript updates, and a keyboard path to the text fallback.

**Files.** `apps/web/components/interview/live-room.tsx`, `control-bar.tsx`,
`transcript-panel.tsx`, `text-fallback.tsx`, `voice-stage.tsx`.

**Acceptance.** Interactive controls have accessible names and visible focus;
the transcript panel is an `aria-live` region; the screen is fully keyboard
operable end-to-end; no new axe/Lighthouse a11y violations. Document what you
tested (screen reader + keyboard) in the PR.

---

### 5. 🟢 Add a 4th avatar persona prompt

**Problem.** The avatar library ships three personas — `anime`, `superhero`,
`recruiter` (`apps/web/lib/personas.ts`, `scripts/veo/prompts.ts`). Add a fourth
(e.g. a calm "professor" / academic interviewer) so users have more variety.

**Files.** `scripts/veo/prompts.ts` (add the IP-safe `reference` / `idle` /
`speaking` prompt set + extend `PersonaId`), `apps/web/lib/personas.ts` (mirror
the new `PersonaId` + metadata + poster/idle/speaking URLs).

**Acceptance.** The new persona appears in the avatar gallery; `PersonaId` stays
in sync across both files; the Veo prompt carries the existing IP-safety clause
(original fictional character, no real person/franchise, no brand logos);
`pnpm typecheck` green. You do **not** need to render real video — placeholder
asset URLs are fine for the PR.

---

### 6. 🟡 Surface skill-library retrieval in the report

**Problem.** The agent has a skill library / distiller
(`apps/agent/.../skilllib/`) that can surface reusable company playbooks and
rubric hits, but the report screen doesn't show which skills informed the
interview. Make that visible to the candidate.

**Files.** `apps/web/app/report/[id]/page.tsx`, a new
`apps/web/components/report/` component, and (if a contract field is needed)
`packages/shared` + the agent's mirrored Pydantic model.

**Acceptance.** When skilllib data is present on the session, the report renders
a tasteful "informed by" section; when absent (sample/offline), the report still
renders cleanly. Any new contract field has TS ↔ Pydantic parity. `pnpm build`
green.

---

### 7. 🟡 Add a real Paddle webhook signature-verification test

**Problem.** The billing webhook (`apps/web/app/api/billing/webhook/route.ts`)
verifies Paddle signatures via `verifyPaddleWebhook` in
`apps/web/lib/billing-server.ts`, but there's no test pinning the documented
status contract (501 when unconfigured, 400 on missing/invalid signature, 200 on
accepted).

**Files.** a new test under `apps/web` (co-located test or `tests/`),
`apps/web/lib/billing-server.ts` (read the signature scheme), `route.ts` (the
contract under test).

**Acceptance.** Tests assert: unconfigured → 501; missing/invalid signature →
400; valid signature with an ignored event type → 200. No real Paddle secret
required — drive it with a test secret/env. `pnpm test` green.

---

### 8. 🟠 Add `GET /api/session/[id]` so the report reads live data

**Problem.** `apps/web/app/report/[id]/page.tsx` reads the `sessions` row
directly from Supabase and falls back to sample data offline. There is no
`GET /api/session/[id]` route, which makes the session payload hard to fetch
from elsewhere (e.g. polling, the CLI, or a future client). Add one.

**Files.** new `apps/web/app/api/session/[id]/route.ts`,
`apps/web/lib/supabase/server.ts` (reuse the client), optionally refactor
`report/[id]/page.tsx` to consume it.

**Acceptance.** `GET /api/session/[id]` returns the session's `scorecard` +
`context` (zod-validated) for an authorized user, 404 on miss, and a safe
offline response when Supabase is unconfigured (mirroring the page's
sample-fallback behavior). RLS/authorization respected — a user can only read
their own session. `pnpm typecheck` green.

---

### 9. 🟢 Record the hero `demo.gif` for the README

**Problem.** The README's hero slot needs a short looping demo of a real mock
interview (setup → live voice → report). This is a non-code contribution that
makes the project far more legible at first glance.

**Files.** `assets/` (add `demo.gif`), `README.md` hero
reference, `assets/README.md` (note the source/dimensions).

**Acceptance.** A short (<~15s), reasonably sized looping GIF/anim showing the
core loop, referenced from both READMEs, with no real candidate PII on screen
(use the offline sample data). Note capture settings in `assets/README.md`.

---

### 10. 🟠 Make interview metering a DB-atomic increment

**Problem.** `apps/web/app/setup/actions.ts` meters voice interviews with a
non-atomic read-then-write
(`.update({ interviews_used: (profile.interviews_used ?? 0) + 1 })`). Two
concurrent session starts can race and under-count usage — which matters because
the per-tier cap is enforced in code (golden rule 5). Move the increment into an
atomic DB operation.

**Files.** `apps/web/app/setup/actions.ts`, a new Supabase migration under
`supabase/migrations/` adding an `increment_interviews_used` RPC (atomic
`UPDATE ... SET interviews_used = interviews_used + 1` that also respects the
cap), and `apps/web/lib/plan.ts` (the cap source of truth, for reference).

**Acceptance.** The increment is a single atomic statement / RPC (no
read-then-write in app code); the cap from `plan.ts` is honored server-side;
overage still routes to the credit ledger as before; behavior is unchanged when
Supabase is unconfigured (offline path). Include the migration. `pnpm typecheck`
green.

---

Don't see your idea here? Open a [feature request](../.github/ISSUE_TEMPLATE/feature_request.yml)
or start a Discussion. Bigger pieces of work are tracked as the work packages
(WP-0…WP-13) in
[`site/AI-Interviewer-Build-Handoff.md`](../site/AI-Interviewer-Build-Handoff.md) §16.
