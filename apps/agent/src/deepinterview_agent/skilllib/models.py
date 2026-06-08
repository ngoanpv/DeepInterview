"""Pydantic models for the WP-10 self-evolving skill library.

A *skill* is a Markdown file with YAML frontmatter: the frontmatter is the
machine-readable :class:`SkillFrontmatter` (the 9 fields in ``skills/SCHEMA.md``)
and the body is free-form Markdown (round structure, question bank, signals,
pitfalls). A :class:`SkillDraft` is a proposed delta sitting in the review queue
(``skills/_review/``); it is never part of the live library until ``promote``
writes it out.

``last_verified`` is an ISO-8601 *date string* (e.g. ``"2026-06-08"``), NOT a
``datetime.date`` — YAML parses an unquoted date into a ``date`` object, so the
store coerces it back to a string before constructing the model.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SkillStatus = Literal["draft", "review", "promoted", "deprecated"]


class SkillFrontmatter(BaseModel):
    """Machine-readable header of a skill file (mirrors ``skills/SCHEMA.md``)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    company: str
    role: str
    level: str
    competency: list[str] = Field(default_factory=list)
    version: int = 1
    source_runs: int = 0
    confidence: float = 0.3
    last_verified: str
    status: SkillStatus = "draft"


class Skill(BaseModel):
    """A full skill: structured frontmatter + free-form Markdown body."""

    model_config = ConfigDict(extra="forbid")

    frontmatter: SkillFrontmatter
    body_md: str


class SkillDraft(BaseModel):
    """A proposed skill delta distilled from one session (review-queue only)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    target_skill_id: str
    frontmatter: SkillFrontmatter
    body_md: str
    source_session_id: str
    created_at: str
