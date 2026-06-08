"""Read/write skill files (Markdown + YAML frontmatter) and retrieve them.

File format::

    ---
    id: examplecorp-backend-senior
    company: ExampleCorp
    ...
    ---
    # body markdown...

The store is the only place that knows this on-disk shape. ``find_relevant`` is
deliberately *targeted*: it loads only the skill(s) matching ``company × role``
(optionally ``level``) rather than all-loading the library, protecting prep
latency/cost as the library grows.

YAML quirk handled here: an unquoted ``last_verified: 2026-06-08`` parses to a
``datetime.date``, which a ``str``-typed Pydantic field will reject — so frontmatter
date/datetime values are coerced to ISO strings before model construction.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import yaml

from .models import Skill, SkillFrontmatter

# skilllib/ -> deepinterview_agent/ -> src/ -> agent/ -> apps/ -> <repo root>
_REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_SKILLS_DIR = _REPO_ROOT / "skills"

_FENCE = "---"


def default_skills_dir() -> Path:
    """Return the repo-root ``skills/`` directory (the live library)."""
    return DEFAULT_SKILLS_DIR


def slugify(*, company: str, role: str, level: str) -> str:
    """Canonical ``{company}-{role}-{level}`` slug used for id + filename + merge.

    Lowercased; runs of non-alphanumeric chars collapse to a single hyphen.
    """
    raw = f"{company}-{role}-{level}".lower()
    cleaned: list[str] = []
    prev_dash = False
    for ch in raw:
        if ch.isalnum():
            cleaned.append(ch)
            prev_dash = False
        elif not prev_dash:
            cleaned.append("-")
            prev_dash = True
    return "".join(cleaned).strip("-")


def _coerce_scalars(data: dict) -> dict:
    """Coerce YAML date/datetime values to ISO strings (frontmatter is all str-safe)."""
    out: dict = {}
    for key, value in data.items():
        if isinstance(value, (_dt.date, _dt.datetime)):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


def parse_skill(text: str) -> Skill:
    """Parse a ``---\\nfrontmatter\\n---\\nbody`` string into a :class:`Skill`."""
    if not text.lstrip().startswith(_FENCE):
        raise ValueError("skill file must start with a '---' frontmatter fence")
    # Split into ['', frontmatter, body] on the first two fences.
    stripped = text.lstrip("\n")
    parts = stripped.split(_FENCE, 2)
    if len(parts) < 3:
        raise ValueError("skill file is missing the closing '---' frontmatter fence")
    _, raw_front, body = parts
    data = yaml.safe_load(raw_front) or {}
    if not isinstance(data, dict):
        raise ValueError("skill frontmatter must be a YAML mapping")
    frontmatter = SkillFrontmatter.model_validate(_coerce_scalars(data))
    return Skill(frontmatter=frontmatter, body_md=body.lstrip("\n"))


def serialize_skill(skill: Skill) -> str:
    """Serialize a :class:`Skill` back to the ``---\\n...\\n---\\nbody`` format."""
    front = yaml.safe_dump(
        skill.frontmatter.model_dump(),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    body = skill.body_md.rstrip("\n")
    return f"{_FENCE}\n{front}{_FENCE}\n\n{body}\n"


def load_skill(path: str | Path) -> Skill:
    """Load and parse a single skill file."""
    return parse_skill(Path(path).read_text(encoding="utf-8"))


def save_skill(skill: Skill, path: str | Path) -> Path:
    """Serialize and write a skill to ``path`` (creating parent dirs)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(serialize_skill(skill), encoding="utf-8")
    return p


def _is_skill_file(path: Path) -> bool:
    """A skill file is a ``*.md`` whose content opens with a frontmatter fence."""
    if path.suffix != ".md":
        return False
    try:
        with path.open("r", encoding="utf-8") as fh:
            head = fh.read(8)
    except OSError:
        return False
    return head.lstrip().startswith(_FENCE)


def list_skills(skills_dir: str | Path | None = None) -> list[Skill]:
    """Load every *live* skill in ``skills_dir`` (top level only).

    Skips ``README.md`` / ``SCHEMA.md`` (no frontmatter) and the ``_review/``
    queue subdirectory. Files that fail to parse are skipped, not raised.
    """
    root = Path(skills_dir) if skills_dir is not None else DEFAULT_SKILLS_DIR
    if not root.exists():
        return []
    skills: list[Skill] = []
    for path in sorted(root.glob("*.md")):
        if not _is_skill_file(path):
            continue
        try:
            skills.append(load_skill(path))
        except (ValueError, yaml.YAMLError):
            continue
    return skills


def find_relevant(
    skills_dir: str | Path | None = None,
    *,
    company: str,
    role: str,
    level: str | None = None,
) -> list[Skill]:
    """Return live skills matching ``company`` + ``role`` (and ``level`` if given).

    Matching is case-insensitive and exact on company/role/level. Deprecated
    skills are excluded. Only the matching playbook(s) are returned — callers
    must not all-load the library.
    """
    want_company = company.strip().lower()
    want_role = role.strip().lower()
    want_level = level.strip().lower() if level else None

    matches: list[Skill] = []
    for skill in list_skills(skills_dir):
        fm = skill.frontmatter
        if fm.status == "deprecated":
            continue
        if fm.company.strip().lower() != want_company:
            continue
        if fm.role.strip().lower() != want_role:
            continue
        if want_level is not None and fm.level.strip().lower() != want_level:
            continue
        matches.append(skill)
    return matches
