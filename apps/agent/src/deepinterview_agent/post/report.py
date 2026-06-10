"""ScoreCard assembly for the WP-7 scoring pipeline.

:func:`generate_report` takes the per-competency scores and the language report
and assembles the final :class:`ScoreCard`:

* ``overall_score`` is the mean of the competency scores, clamped to 0-5 (0.0
  when there are no competencies).
* ``weak_competencies`` is exactly the set of competencies whose band is
  ``weak`` or ``developing`` — the list the Prep Coach loop consumes to decide
  what to teach next. It is a subset of the scorecard's competencies.
* ``model_answers`` holds one improved answer per planned question.
* strengths / weaknesses / next_steps / summary are written by the LLM.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from ..core.logging import get_logger
from ..shared_models import ModelAnswer, ScoreCard
from .prompts import model_answer_prompts, report_summary_prompts

if TYPE_CHECKING:
    from ..core.deps import Deps
    from ..shared_models import CompetencyScore, InterviewContext, LanguageReport

log = get_logger(__name__)

_WEAK_LEVELS = frozenset({"weak", "developing"})

# Bound concurrent model-answer drafts (same rationale as the evaluator).
_MAX_CONCURRENT_DRAFTS = 4


class _ReportNarrative(BaseModel):
    """Free-text narrative the LLM fills; numeric fields are assembled separately."""

    model_config = ConfigDict(extra="forbid")
    strengths: list[str]
    weaknesses: list[str]
    next_steps: list[str]
    summary: str


def _overall_score(comp_scores: list[CompetencyScore]) -> float:
    """Mean competency score, clamped to 0-5; 0.0 for an empty list."""
    if not comp_scores:
        return 0.0
    mean = sum(cs.score for cs in comp_scores) / len(comp_scores)
    return max(0.0, min(5.0, mean))


def _weak_competencies(comp_scores: list[CompetencyScore]) -> list[str]:
    """Competencies whose band is weak/developing (de-duplicated, order-preserving)."""
    seen: set[str] = set()
    weak: list[str] = []
    for cs in comp_scores:
        if cs.level in _WEAK_LEVELS and cs.competency not in seen:
            seen.add(cs.competency)
            weak.append(cs.competency)
    return weak


def _coverage_pct(ctx: InterviewContext) -> float:
    """Fraction of planned questions that received a non-empty answer.

    1.0 when nothing was planned (vacuously complete). This is the signal that
    tells a low ``overall_score`` from a short/aborted interview apart from one
    earned by genuinely weak answers.
    """
    total = len(ctx.plan.questions)
    if total == 0:
        return 1.0
    answered_ids = {a.question_id for a in ctx.answers if a.transcript and a.transcript.strip()}
    answered = sum(1 for q in ctx.plan.questions if q.id in answered_ids)
    return answered / total


def _competency_lines(comp_scores: list[CompetencyScore]) -> str:
    if not comp_scores:
        return "- (no competencies scored)"
    return "\n".join(
        f"- {cs.competency}: {cs.score:.1f}/5 ({cs.level}) — {cs.evidence}" for cs in comp_scores
    )


async def _model_answers(ctx: InterviewContext, deps: Deps) -> list[ModelAnswer]:
    """Draft one improved answer per ANSWERED question (concurrent, isolated).

    Only questions the candidate actually reached get a model answer — drafting
    for never-asked questions burns LLM calls on content the report can't ground
    (cost rule #5) and risks blowing the single stage timeout on long plans. A
    failed draft drops that one answer instead of voiding the stage.
    """
    by_question = {a.question_id: a for a in ctx.answers}
    answered = [
        (q, by_question[q.id].transcript)
        for q in ctx.plan.questions
        if q.id in by_question and (by_question[q.id].transcript or "").strip()
    ]

    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_DRAFTS)

    async def _draft(question, transcript):  # noqa: ANN001, ANN202
        async with semaphore:
            try:
                system, user = model_answer_prompts(question, ctx.candidate, transcript)
                text = await deps.llm.complete_text(system=system, user=user)
                return ModelAnswer(question_id=question.id, answer=text)
            except Exception:  # noqa: BLE001 - isolate: one bad draft must not void the rest
                log.exception("report: model answer failed for question %s; skipping", question.id)
                return None

    results = await asyncio.gather(*(_draft(q, t) for q, t in answered))
    return [r for r in results if r is not None]


async def generate_report(
    ctx: InterviewContext,
    comp_scores: list[CompetencyScore],
    lang_report: LanguageReport,
    deps: Deps,
) -> ScoreCard:
    """Assemble the final :class:`ScoreCard` from the scored components."""
    overall = _overall_score(comp_scores)
    weak = _weak_competencies(comp_scores)

    system, user = report_summary_prompts(ctx, _competency_lines(comp_scores), overall)
    narrative = await deps.llm.complete_json(system=system, user=user, schema=_ReportNarrative)
    model_answers = await _model_answers(ctx, deps)

    return ScoreCard(
        overall_score=overall,
        competency_scores=comp_scores,
        strengths=narrative.strengths,
        weaknesses=narrative.weaknesses,
        weak_competencies=weak,
        model_answers=model_answers,
        next_steps=narrative.next_steps,
        language_report=lang_report,
        summary=narrative.summary,
        coverage_pct=_coverage_pct(ctx),
    )
