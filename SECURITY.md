# Security Policy

DeepInterview is a voice-first AI mock-interview platform. It handles candidate
CVs, job descriptions, interview transcripts, and recordings — so we take
security and privacy seriously and welcome responsible disclosure.

## Reporting a vulnerability

**Please do not report security issues in public GitHub issues, Discussions, or
pull requests.** A public report tells attackers about the problem before a fix
exists.

Instead, email **security@deepinterview.dev** with:

- a description of the issue and the impact you believe it has;
- the affected component (`apps/web`, `apps/agent`, `services/lightrag`, `cli`,
  `packages/shared`, `ee/`, infra, or a dependency);
- step-by-step reproduction instructions or a proof-of-concept; and
- any relevant logs, requests, or screenshots (please redact secrets and
  personal data).

We aim to acknowledge reports within a few business days and will keep you
updated as we investigate. We ask that you give us reasonable time to ship a fix
before any public disclosure, and that your testing does not access, modify, or
destroy data that is not your own. We are happy to credit reporters in the
release notes unless you prefer to remain anonymous.

For sensitive reports you may encrypt your email; request our PGP key in an
initial (non-sensitive) message to the same address.

## Supported versions

DeepInterview is **pre-v0.1 and under active development** — there is no
generally available release line yet. During this phase, security fixes land on
the default branch (`main`) only; there are no maintained back-ports. Always run
the latest `main` (or the latest tagged pre-release, once tags exist) to receive
fixes.

| Version          | Supported                          |
| ---------------- | ---------------------------------- |
| `main` (pre-v0.1) | ✅ Fixes land here                  |
| Older checkouts  | ❌ Please update to latest `main`   |

This table will be replaced with a real version matrix once we cut `v0.1`.

## Secrets and configuration

DeepInterview is **secrets-via-env-vars only**. To keep credentials out of the
codebase and out of git history:

- **Never commit `.env`, `.env.local`, real keys, tokens, or recordings.** Only
  `.env.example` (placeholder values, no real secrets) belongs in version
  control. `.env*` is already covered by `.gitignore` — keep it that way.
- Supply all provider credentials (LLM, STT, TTS, search, Supabase, Cloudflare
  R2, LiveKit, billing) through environment variables, never hard-coded
  defaults.
- The Supabase **service-role key** bypasses Row Level Security. It is
  server-only — never expose it to the browser, a `NEXT_PUBLIC_*` variable, or
  client bundles.
- If a secret is ever committed, treat it as compromised: **rotate the
  credential first**, then remove it from history. Rotation matters more than
  the scrub, because the old value is already public.
- The offline / mock-first path runs the full prep → live → post loop **with no
  API keys at all**. Prefer it for local development and CI so you are not
  handling real credentials unless you need to.

## Enterprise (`ee/`) licensing note

Code under the top-level `ee/` directory is **not** part of the AGPLv3 open-source
core. It is distributed under a **separate commercial license** (see
[`ee/LICENSE`](ee/LICENSE) and [`ee/README.md`](ee/README.md)). Security reports
that touch `ee/` are handled through the same `security@deepinterview.dev`
channel, but any disclosure, redistribution, or reuse of `ee/` code remains
governed by its commercial license terms rather than the AGPLv3 that covers the
rest of the repository.
