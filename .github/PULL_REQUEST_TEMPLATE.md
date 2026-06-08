<!--
Thanks for contributing to DeepInterview! Keep PRs small — one work package
(or one focused change) per PR. See CONTRIBUTING.md for the full workflow.
-->

## Summary

<!-- What does this PR do, and why? One or two sentences. -->

## Linked issue

<!-- e.g. "Closes #123" / "Part of #123". Use "Closes" to auto-close on merge. -->

Closes #

## Work package

<!-- Which WP does this touch? See AI-Interviewer-Build-Handoff.md §16. -->

- [ ] WP-0 — Monorepo + shared contracts + CLI scaffold
- [ ] WP-1 — Web: auth + setup/onboarding
- [ ] WP-2 — Web: live interview screen
- [ ] WP-3 — Web: report / feedback screen
- [ ] WP-4 — Web: Prep Coach UI
- [ ] WP-5 — Agent: live voice interviewer
- [ ] WP-6 — Agent: prep pipeline
- [ ] WP-7 — Agent: scoring pipeline
- [ ] WP-8 — Knowledge service (LightRAG)
- [ ] WP-9 — Avatar system
- [ ] WP-10 — Skill library + distiller
- [ ] WP-11 — Payments + plan gating
- [ ] WP-12 — DevOps / deploy / observability
- [ ] WP-13 — OSS launch assets
- [ ] Other / cross-cutting (docs, chore, CI)

## Checklist

- [ ] Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
      (`feat:`, `fix:`, `docs:`, `chore:`, …).
- [ ] `pnpm build` is green.
- [ ] `pnpm typecheck` is green.
- [ ] `pnpm lint` is green.
- [ ] `pnpm test` is green.
- [ ] `uv --directory apps/agent run pytest` is green (if Python touched).
- [ ] The **offline / mock-first** path still works with **no API keys set**
      (no provider key required to run the prep → live → post loop locally).
- [ ] No secrets committed (`.env*`, real keys/tokens, recordings).
- [ ] Docs updated where behavior or contracts changed (README, `docs/`,
      `packages/shared` contract docs, or the handoff spec).
- [ ] Shared contracts stay in sync: TS ↔ Pydantic parity holds
      (`packages/shared` + the agent parity test) if I changed any contract.

## Screenshots / recordings

<!-- REQUIRED for any UI change. Before/after images or a short clip.
     Delete this section only if the PR has no user-facing UI. -->

## Notes for reviewers

<!-- Anything tricky, follow-ups, or out-of-scope items intentionally left. -->
