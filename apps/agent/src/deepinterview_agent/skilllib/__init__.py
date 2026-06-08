"""WP-10: the self-evolving skill library + distiller.

A growing, reusable library of company interview playbooks and scoring-rubric
calibration, stored as Markdown + YAML frontmatter under the repo-root
``skills/`` directory and git-tracked. The quality gate is **distill → review →
promote**: the post-interview distiller (:func:`propose_skill`) PROPOSES a delta
into ``skills/_review/`` (never auto-merging), a reviewer approves it, and
:func:`promote` bumps the version, dedupes the question bank, raises confidence,
and scrubs PII before the skill enters the live library.

Public surface:
    - ``propose_skill``  — distill a draft into the review queue
    - ``promote``        — promote a reviewed draft into the live library
    - ``find_relevant``  — targeted retrieval for the prep planner
    - ``load_skill`` / ``save_skill`` — read/write a single skill file
"""

from __future__ import annotations

from .distiller import propose_skill
from .models import Skill, SkillDraft, SkillFrontmatter
from .promote import promote
from .scrub import scrub_pii
from .store import find_relevant, list_skills, load_skill, save_skill, slugify

__all__ = [
    "Skill",
    "SkillDraft",
    "SkillFrontmatter",
    "find_relevant",
    "list_skills",
    "load_skill",
    "promote",
    "propose_skill",
    "save_skill",
    "scrub_pii",
    "slugify",
]
