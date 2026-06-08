# skills/ — Company playbooks + rubrics

Versioned, git-tracked **company interview playbooks** and **scoring rubrics**, stored as
**Markdown + YAML frontmatter**. This is the data moat: de-identified, generalized playbooks
promoted from real interview runs (`{company} × {role} × {level}`).

- Each file = one skill. Frontmatter schema: see [`SCHEMA.md`](./SCHEMA.md).
- A **distill → review → promote** pipeline (WP-10) proposes deltas to a review queue;
  nothing auto-merges. Promotion bumps `version`, dedupes, and **scrubs PII**.
- Always attach provenance ("based on N reports, last verified Z"); company facts pass a
  human/LLM review gate to avoid compounding hallucinated claims.

`example-corp-backend-senior.md` is a **fictional** sample showing the format.
