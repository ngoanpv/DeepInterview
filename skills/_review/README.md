# skills/_review/ — un-promoted skill drafts (WP-10)

This directory is the **review queue**. The post-interview distiller
(`skilllib.propose_skill`) writes proposed skill deltas here as
`<draft_id>.md` — it **never** auto-merges into the live library above.

A human (or LLM) reviewer reads a draft, then `skilllib.promote(draft_path)`
bumps `version`, dedupes/merges the question bank, raises `confidence`, scrubs
PII again as a safety net, and writes the result into the live `skills/` root.

Drafts here are scratch and may contain machine-extracted text. PII is scrubbed
at propose time, but treat this queue as transient: do **not** commit real
candidate drafts. Only `.gitkeep` and this README are meant to live in git.
