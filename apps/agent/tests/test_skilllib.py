"""Offline tests for the WP-10 skill library + distiller (MockLLM, no network).

Covers the store round-trip and targeted retrieval, the PII scrubber, the
distiller's PROPOSE-only contract (drafts land in ``skills/_review/`` and never
the live root, candidate PII is scrubbed), and promotion (create + merge with
version bump, status flip, and a PII safety-net pass). All writes that mutate a
library happen under ``tmp_path`` so the committed ``skills/`` library is never
polluted with candidate data.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from deepinterview_agent.core.deps import build_deps
from deepinterview_agent.prep import run_prep
from deepinterview_agent.shared_models import AnswerRecord, LanguageMode, PrepRequest
from deepinterview_agent.skilllib import (
    find_relevant,
    load_skill,
    promote,
    propose_skill,
    save_skill,
    scrub_pii,
    slugify,
)
from deepinterview_agent.skilllib.distiller import REVIEW_SUBDIR
from deepinterview_agent.skilllib.models import Skill, SkillFrontmatter
from deepinterview_agent.skilllib.store import DEFAULT_SKILLS_DIR

# --- fixtures ----------------------------------------------------------------

_CANDIDATE_NAME = "Jane Q. Doe"
_CANDIDATE_EMAIL = "jane.doe@personalmail.example"
_CANDIDATE_PHONE = "+1 (415) 555-0199"


def _request() -> PrepRequest:
    return PrepRequest(
        cv_url="https://example.com/cv.pdf",
        jd_text="Senior Backend Engineer building distributed payment systems in Python.",
        company="ExampleCorp",
        language_mode=LanguageMode(primary="en", mixed=False),
    )


def _sample_skill() -> Skill:
    fm = SkillFrontmatter(
        id="examplecorp-backend-engineer-senior",
        company="ExampleCorp",
        role="backend-engineer",
        level="senior",
        competency=["system-design", "communication"],
        version=2,
        source_runs=3,
        confidence=0.55,
        last_verified="2026-06-08",
        status="promoted",
    )
    body = (
        "# ExampleCorp — Senior Backend Engineer\n\n"
        "## Round structure\n1. Intro\n2. System design\n\n"
        "## Question bank\n"
        '- "Design a multi-region rate limiter." (technical, target: system-design)\n\n'
        "## Signals\n- Reasons about trade-offs explicitly.\n\n"
        "## Pitfalls\n- Jumps to code before clarifying requirements.\n"
    )
    return Skill(frontmatter=fm, body_md=body)


# --- store: round-trip + targeted retrieval ----------------------------------


def test_store_round_trips_a_skill(tmp_path: Path) -> None:
    skill = _sample_skill()
    path = tmp_path / "examplecorp-backend-engineer-senior.md"
    save_skill(skill, path)

    loaded = load_skill(path)
    assert loaded.frontmatter == skill.frontmatter
    assert loaded.body_md.strip() == skill.body_md.strip()
    # last_verified stays a string even though YAML would parse it as a date.
    assert loaded.frontmatter.last_verified == "2026-06-08"
    assert isinstance(loaded.frontmatter.last_verified, str)


def test_find_relevant_matches_company_and_role_only(tmp_path: Path) -> None:
    save_skill(_sample_skill(), tmp_path / "examplecorp-backend-engineer-senior.md")
    # A non-matching skill for a different company/role.
    other = _sample_skill().model_copy(deep=True)
    other.frontmatter.id = "othercorp-frontend-junior"
    other.frontmatter.company = "OtherCorp"
    other.frontmatter.role = "frontend-engineer"
    other.frontmatter.level = "junior"
    save_skill(other, tmp_path / "othercorp-frontend-junior.md")

    hits = find_relevant(tmp_path, company="ExampleCorp", role="backend-engineer")
    assert len(hits) == 1
    assert hits[0].frontmatter.company == "ExampleCorp"

    # The non-matching skill is never returned.
    assert find_relevant(tmp_path, company="OtherCorp", role="backend-engineer") == []
    # Level filter narrows further.
    assert find_relevant(
        tmp_path, company="ExampleCorp", role="backend-engineer", level="staff"
    ) == []


def test_find_relevant_loads_committed_example() -> None:
    """The committed fictional example is parseable and retrievable by company+role."""
    hits = find_relevant(DEFAULT_SKILLS_DIR, company="ExampleCorp", role="backend-engineer")
    ids = {h.frontmatter.id for h in hits}
    assert "examplecorp-backend-senior" in ids
    # README.md / SCHEMA.md (no frontmatter) are skipped, not raised.
    assert find_relevant(DEFAULT_SKILLS_DIR, company="Nope", role="nobody") == []


# --- scrub -------------------------------------------------------------------


def test_scrub_pii_removes_name_email_and_phone() -> None:
    text = (
        f"{_CANDIDATE_NAME} answered well. Reach at {_CANDIDATE_EMAIL} "
        f"or call {_CANDIDATE_PHONE} anytime."
    )
    scrubbed = scrub_pii(text, names=[_CANDIDATE_NAME])

    assert "Jane" not in scrubbed
    assert _CANDIDATE_EMAIL not in scrubbed
    assert "555-0199" not in scrubbed
    assert "[candidate]" in scrubbed
    assert "[email]" in scrubbed
    assert "[phone]" in scrubbed
    # Idempotent.
    assert scrub_pii(scrubbed, names=[_CANDIDATE_NAME]) == scrubbed


# --- distiller: PROPOSE only --------------------------------------------------


def _prepared_session_with_pii(deps) -> str:
    """run_prep, then seed a distinctive name + a PII-laden answer transcript."""
    session_id = asyncio.run(run_prep(_request(), deps))
    ctx = asyncio.run(deps.repo.load_context(session_id))
    assert ctx is not None
    # Override the mock candidate name with something distinctive to scrub.
    ctx.candidate.name = _CANDIDATE_NAME
    questions = ctx.plan.questions
    assert questions
    ctx.answers.append(
        AnswerRecord(
            question_id=questions[0].id,
            transcript=(
                f"My name is {_CANDIDATE_NAME}, you can reach me at {_CANDIDATE_EMAIL} "
                f"or {_CANDIDATE_PHONE}. I designed a service with idempotent retries."
            ),
            started_at="2026-06-08T09:00:00Z",
            ended_at="2026-06-08T09:02:00Z",
            duration_sec=120.0,
        )
    )
    asyncio.run(deps.repo.save_context(session_id, ctx))
    return session_id


def test_propose_skill_writes_draft_to_review_only_and_scrubs_pii(tmp_path: Path) -> None:
    deps = build_deps()
    session_id = _prepared_session_with_pii(deps)

    draft = asyncio.run(propose_skill(session_id, deps, skills_dir=tmp_path))

    # Draft is a 'draft', sourced from 1 run, with a modest confidence.
    assert draft.frontmatter.status == "draft"
    assert draft.frontmatter.source_runs == 1
    assert 0.0 < draft.frontmatter.confidence <= 0.4
    assert draft.source_session_id == session_id

    # The draft file exists in the review queue and NOT in the live root.
    review_path = tmp_path / REVIEW_SUBDIR / f"{draft.id}.md"
    assert review_path.exists(), "draft must be written to the review queue"
    live_files = list(tmp_path.glob("*.md"))
    assert live_files == [], "propose_skill must NOT write into the live library root"

    # PII from the candidate name is scrubbed from the body the distiller built.
    assert "Jane" not in draft.body_md
    assert "[candidate]" in draft.body_md
    # And the on-disk draft is scrubbed too.
    assert "Jane" not in review_path.read_text(encoding="utf-8")


# --- promote -----------------------------------------------------------------


def test_promote_creates_new_skill_with_promoted_status(tmp_path: Path) -> None:
    deps = build_deps()
    session_id = _prepared_session_with_pii(deps)
    draft = asyncio.run(propose_skill(session_id, deps, skills_dir=tmp_path))
    draft_path = tmp_path / REVIEW_SUBDIR / f"{draft.id}.md"

    out_path = promote(draft_path, skills_dir=tmp_path)

    assert out_path.exists()
    assert out_path.parent == tmp_path  # written into the live root, not _review.
    promoted = load_skill(out_path)
    assert promoted.frontmatter.status == "promoted"
    assert promoted.frontmatter.id == slugify(
        company=draft.frontmatter.company,
        role=draft.frontmatter.role,
        level=draft.frontmatter.level,
    )
    # PII safety-net: still clean after promotion.
    assert "Jane" not in promoted.body_md


def test_promote_merges_and_bumps_version_when_skill_exists(tmp_path: Path) -> None:
    deps = build_deps()
    session_id = _prepared_session_with_pii(deps)
    draft = asyncio.run(propose_skill(session_id, deps, skills_dir=tmp_path))
    draft_path = tmp_path / REVIEW_SUBDIR / f"{draft.id}.md"

    # Seed an existing live skill with the same slug to force a merge.
    slug = slugify(
        company=draft.frontmatter.company,
        role=draft.frontmatter.role,
        level=draft.frontmatter.level,
    )
    existing = Skill(
        frontmatter=SkillFrontmatter(
            id=slug,
            company=draft.frontmatter.company,
            role=draft.frontmatter.role,
            level=draft.frontmatter.level,
            competency=["pre-existing-competency"],
            version=4,
            source_runs=9,
            confidence=0.6,
            last_verified="2026-01-01",
            status="promoted",
        ),
        body_md=(
            "# Existing\n\n## Question bank\n"
            '- "An already-known question." (technical, target: x)\n'
        ),
    )
    save_skill(existing, tmp_path / f"{slug}.md")

    out_path = promote(draft_path, skills_dir=tmp_path)
    merged = load_skill(out_path)

    assert merged.frontmatter.version == 5, "version must bump on merge"
    assert merged.frontmatter.source_runs == 10, "source_runs must increment"
    assert merged.frontmatter.confidence > 0.6, "confidence must rise modestly"
    assert merged.frontmatter.confidence <= 0.95
    assert merged.frontmatter.status == "promoted"
    # The pre-existing question is retained; the bank is merged (deduped).
    assert "An already-known question." in merged.body_md
    assert "Jane" not in merged.body_md


def test_propose_default_dir_writes_to_review_only(
    tmp_path: Path, monkeypatch
) -> None:
    """Guard the no-``skills_dir`` branch without touching the committed library.

    Point the distiller's default at ``tmp_path`` so the default code path is
    exercised but the real ``skills/`` tree is never written to.
    """
    from deepinterview_agent.skilllib import distiller as distiller_mod

    monkeypatch.setattr(distiller_mod, "DEFAULT_SKILLS_DIR", tmp_path)

    deps = build_deps()
    session_id = _prepared_session_with_pii(deps)
    draft = asyncio.run(propose_skill(session_id, deps))

    assert (tmp_path / REVIEW_SUBDIR / f"{draft.id}.md").exists()
    assert list(tmp_path.glob("*.md")) == [], "default branch must not write live skills"
