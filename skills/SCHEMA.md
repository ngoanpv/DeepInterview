# Skill frontmatter schema

Every skill file begins with YAML frontmatter:

| Field | Type | Notes |
|---|---|---|
| `id` | string | Stable slug, e.g. `examplecorp-backend-senior`. |
| `company` | string | Company name (or `generic` for role/competency skills). |
| `role` | string | e.g. `backend-engineer`. |
| `level` | string | One of `intern, junior, mid, senior, staff, principal`. |
| `competency` | string \| string[] | Target competency entities (shared space with scoring + Prep Coach). |
| `version` | integer | Bumped on promotion. |
| `source_runs` | integer | Number of interview runs this was distilled from. |
| `confidence` | number | 0–1; decays over time. |
| `last_verified` | string | ISO-8601 date. |
| `status` | string | `draft \| review \| promoted \| deprecated`. |

Body sections (free-form Markdown): **Round structure**, **Question bank**, **Signals**, **Pitfalls**.
