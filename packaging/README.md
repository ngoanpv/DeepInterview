# packaging/

Distribution packaging for the `deepinterview` CLI.

- **npm** — NOT yet published. The CLI lives in the `cli/` workspace package
  (`@deepinterview/cli`, marked `private`) and currently runs only from a
  repo checkout: `pnpm build && pnpm deepinterview <command>`. Publishing to
  the npm registry is deferred to a later WP.
- **pip** — a thin Python wrapper so `pipx run deepinterview` works for agent-only
  self-hosters. Deferred to a later WP.
