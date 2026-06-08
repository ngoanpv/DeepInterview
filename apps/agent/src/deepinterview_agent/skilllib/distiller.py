"""Post-interview distiller: PROPOSE a skill delta (never auto-merge).

After a scored interview, :func:`propose_skill` reads the persisted
``InterviewContext`` (+ scorecard) and synthesizes a company × role × level
playbook delta — round structure, a question bank built from the questions that
were actually asked, the signals an interviewer should look for, and pitfalls /
rubric calibration. It builds a :class:`SkillDraft` (``status='draft'``,
``source_runs=1``, modest ``confidence``), SCRUBS PII from the body, and writes
it to the review queue ``skills/_review/<draft_id>.md``.

It NEVER writes into the live library — that only happens via ``promote`` after
a human/LLM review. The LLM is used for a short narrative summary via
``deps.llm.complete_text``; everything structural is derived deterministically
from the context so the draft is reproducible offline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from .models import SkillDraft, SkillFrontmatter
from .scrub import scrub_pii
from .store import DEFAULT_SKILLS_DIR, slugify

if TYPE_CHECKING:
    from ..core.deps import Deps
    from ..shared_models import InterviewContext

REVIEW_SUBDIR = "_review"
_DEFAULT_CONFIDENCE = 0.3


def _session_date(ctx: InterviewContext) -> str:
    """Best ISO date for ``last_verified``: first answer's timestamp, else today."""
    if ctx.answers:
        # started_at is an ISO-8601 string like "2026-06-08T09:00:00Z".
        return ctx.answers[0].started_at[:10]
    return datetime.now(timezone.utc).date().isoformat()


def _question_text(q) -> str:  # noqa: ANN001 - PlannedQuestion (avoid import cycle weight)
    return q.text.get("en") or next(iter(q.text.values()), "")


def _build_body(ctx: InterviewContext, narrative: str) -> str:
    """Assemble the Markdown body from the asked plan + scorecard.

    The provenance line folds in the candidate's name on purpose so the scrub
    pass has real PII to remove (and to prove the gate works downstream).
    """
    job = ctx.job
    plan = ctx.plan
    sc = ctx.scorecard

    title = f"{job.company_name} — {job.title} ({job.seniority})"

    # Round structure from the ordered sections actually planned.
    rounds = "\n".join(
        f"{i}. {section.title()}" for i, section in enumerate(plan.sections_order, start=1)
    ) or "1. (no sections recorded)"

    # Question bank: the questions that were actually asked, in plan order.
    bank_lines = [f'- "{_question_text(q)}" ({q.section}, target: {q.target_competency})'
                  for q in plan.questions]
    question_bank = "\n".join(bank_lines) or "- (no questions recorded)"

    # Signals + pitfalls + rubric calibration from the scorecard, if present.
    if sc is not None:
        signals = "\n".join(f"- {s}" for s in sc.strengths) or "- (none recorded)"
        pitfalls = "\n".join(f"- {w}" for w in sc.weaknesses) or "- (none recorded)"
        calibration = "\n".join(
            f"- {cs.competency}: observed level **{cs.level}** "
            f"(score {cs.score:.1f}) — {cs.evidence}"
            for cs in sc.competency_scores
        ) or "- (no competency scores recorded)"
    else:
        signals = "- (interview not yet scored)"
        pitfalls = "- (interview not yet scored)"
        calibration = "- (interview not yet scored)"

    provenance = (
        f"Distilled from 1 interview run with candidate {ctx.candidate.name} "
        f"(session {ctx.session_id})."
    )

    return (
        f"# {title}\n\n"
        f"> {provenance}\n\n"
        f"## Summary\n{narrative.strip()}\n\n"
        f"## Round structure\n{rounds}\n\n"
        f"## Question bank\n{question_bank}\n\n"
        f"## Signals\n{signals}\n\n"
        f"## Pitfalls\n{pitfalls}\n\n"
        f"## Rubric calibration\n{calibration}\n"
    )


async def propose_skill(
    session_id: str,
    deps: Deps,
    *,
    skills_dir: str | Path | None = None,
    date: str | None = None,
) -> SkillDraft:
    """Propose a skill delta for ``session_id`` into the review queue.

    Loads the session context from ``deps.repo``, synthesizes a playbook draft,
    scrubs PII, writes it to ``skills/_review/<draft_id>.md``, and returns the
    draft. NEVER writes into the live library.
    """
    ctx = await deps.repo.load_context(session_id)
    if ctx is None:
        raise KeyError(f"No persisted context for session_id: {session_id}")

    root = Path(skills_dir) if skills_dir is not None else DEFAULT_SKILLS_DIR
    review_dir = root / REVIEW_SUBDIR

    company = ctx.job.company_name
    role = ctx.job.title
    level = ctx.job.seniority
    target_skill_id = slugify(company=company, role=role, level=level)
    last_verified = date or _session_date(ctx)

    # Short narrative via the LLM; structural fields are derived deterministically.
    system = (
        "You are an interview-prep analyst. In 2-3 sentences, summarize the "
        "reusable, DE-IDENTIFIED takeaways from this interview for future "
        "candidates targeting the same company/role/level. Do not name the "
        "candidate or include any personal contact details."
    )
    user = (
        f"Company: {company}\nRole: {role} ({level})\n"
        f"Sections: {', '.join(ctx.plan.sections_order)}\n"
        f"Questions asked: {len(ctx.plan.questions)}\n"
    )
    narrative = await deps.llm.complete_text(system=system, user=user)

    body = _build_body(ctx, narrative)
    # SCRUB PII before the draft is ever written to disk.
    body = scrub_pii(body, names=[ctx.candidate.name])

    competency = sorted({q.target_competency for q in ctx.plan.questions if q.target_competency})

    draft_id = f"draft_{slugify(company=company, role=role, level=level)}_{uuid4().hex[:8]}"
    frontmatter = SkillFrontmatter(
        id=target_skill_id,
        company=company,
        role=role,
        level=level,
        competency=competency,
        version=1,
        source_runs=1,
        confidence=_DEFAULT_CONFIDENCE,
        last_verified=last_verified,
        status="draft",
    )
    draft = SkillDraft(
        id=draft_id,
        target_skill_id=target_skill_id,
        frontmatter=frontmatter,
        body_md=body,
        source_session_id=session_id,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    # Write ONLY into the review queue — never the live library.
    review_dir.mkdir(parents=True, exist_ok=True)
    draft_path = review_dir / f"{draft_id}.md"
    _write_draft(draft, draft_path)
    return draft


def _write_draft(draft: SkillDraft, path: Path) -> None:
    """Serialize a draft as a frontmatter+body skill file in the review queue."""
    from .models import Skill  # noqa: PLC0415 - local to keep store import surface tight
    from .store import serialize_skill  # noqa: PLC0415

    skill = Skill(frontmatter=draft.frontmatter, body_md=draft.body_md)
    path.write_text(serialize_skill(skill), encoding="utf-8")
