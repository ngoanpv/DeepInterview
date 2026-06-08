"""Promote a reviewed draft into the live skill library (WP-10 quality gate).

:func:`promote` is the *only* path from the review queue into the live
``skills/`` library, and it is NEVER called automatically — a human/LLM reviewer
invokes it after approving a draft in ``skills/_review/``.

If a matching live skill already exists (same ``{company}-{role}-{level}`` slug),
the draft is **merged/deduped**: ``version`` bumps, ``source_runs`` increments,
the question bank is merged uniquely, ``confidence`` rises modestly (capped),
``last_verified`` updates, and ``status`` becomes ``promoted``. Otherwise a new
skill file is created. ``scrub_pii`` runs again as a safety net before writing.
"""

from __future__ import annotations

from pathlib import Path

from .models import Skill, SkillFrontmatter
from .scrub import scrub_pii
from .store import DEFAULT_SKILLS_DIR, load_skill, save_skill, slugify

_CONFIDENCE_STEP = 0.1
_CONFIDENCE_CAP = 0.95
_QUESTION_BANK_HEADING = "## Question bank"


def _parse_draft(draft_path: str | Path) -> Skill:
    """A draft on disk is a frontmatter+body skill file; load it as a Skill."""
    return load_skill(draft_path)


def _extract_question_bank(body: str) -> list[str]:
    """Return the ``- `` bullet lines under the '## Question bank' section."""
    lines = body.splitlines()
    bank: list[str] = []
    in_section = False
    for line in lines:
        if line.strip().startswith("## "):
            in_section = line.strip() == _QUESTION_BANK_HEADING
            continue
        if in_section and line.strip().startswith("- "):
            bank.append(line.strip())
    return bank


def _merge_question_banks(existing_body: str, draft_body: str) -> str:
    """Append unique question-bank bullets from the draft to the existing body."""
    existing = _extract_question_bank(existing_body)
    incoming = _extract_question_bank(draft_body)
    seen = set(existing)
    new_lines = [q for q in incoming if q not in seen]
    if not new_lines:
        return existing_body

    out_lines: list[str] = []
    inserted = False
    in_section = False
    for line in existing_body.splitlines():
        if line.strip().startswith("## "):
            # Leaving the question-bank section: flush new lines before the next heading.
            if in_section and not inserted:
                out_lines.extend(new_lines)
                inserted = True
            in_section = line.strip() == _QUESTION_BANK_HEADING
        out_lines.append(line)
    # Question bank was the last section (no trailing heading after it).
    if in_section and not inserted:
        out_lines.extend(new_lines)
        inserted = True
    return "\n".join(out_lines) + ("\n" if existing_body.endswith("\n") else "")


def _merge_frontmatter(
    existing: SkillFrontmatter, draft: SkillFrontmatter
) -> SkillFrontmatter:
    """Bump version, increment runs, raise confidence, merge competencies."""
    merged_competency = sorted(set(existing.competency) | set(draft.competency))
    new_confidence = min(_CONFIDENCE_CAP, round(existing.confidence + _CONFIDENCE_STEP, 4))
    return existing.model_copy(
        update={
            "version": existing.version + 1,
            "source_runs": existing.source_runs + max(1, draft.source_runs),
            "confidence": new_confidence,
            "competency": merged_competency,
            "last_verified": draft.last_verified,
            "status": "promoted",
        }
    )


def promote(
    draft_path: str | Path,
    skills_dir: str | Path | None = None,
) -> Path:
    """Promote a reviewed draft into the live library; return the written path.

    NEVER called automatically — a reviewer runs this after approving a draft.
    """
    root = Path(skills_dir) if skills_dir is not None else DEFAULT_SKILLS_DIR
    draft = _parse_draft(draft_path)
    dfm = draft.frontmatter

    slug = slugify(company=dfm.company, role=dfm.role, level=dfm.level)
    target_path = root / f"{slug}.md"

    if target_path.exists():
        # Dedupe / merge into the existing skill.
        existing = load_skill(target_path)
        frontmatter = _merge_frontmatter(existing.frontmatter, dfm)
        body = _merge_question_banks(existing.body_md, draft.body_md)
    else:
        # First promotion: take the draft, flip status to promoted.
        frontmatter = dfm.model_copy(update={"id": slug, "status": "promoted"})
        body = draft.body_md

    # Safety net: scrub PII again before anything enters the live library.
    body = scrub_pii(body, names=[])

    skill = Skill(frontmatter=frontmatter, body_md=body)
    return save_skill(skill, target_path)
