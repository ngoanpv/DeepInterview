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

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from ..shared_models import ModelAnswer, ScoreCard
from .prompts import model_answer_prompts, report_summary_prompts

if TYPE_CHECKING:
    from ..core.deps import Deps
    from ..shared_models import CompetencyScore, InterviewContext, LanguageReport

_WEAK_LEVELS = frozenset({"weak", "developing"})


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


def _competency_lines(comp_scores: list[CompetencyScore]) -> str:
    if not comp_scores:
        return "- (no competencies scored)"
    return "\n".join(
        f"- {cs.competency}: {cs.score:.1f}/5 ({cs.level}) — {cs.evidence}" for cs in comp_scores
    )


async def _model_answers(ctx: InterviewContext, deps: Deps) -> list[ModelAnswer]:
    """Draft one improved answer per planned question."""
    by_question = {a.question_id: a for a in ctx.answers}
    answers: list[ModelAnswer] = []
    for question in ctx.plan.questions:
        answered = by_question.get(question.id)
        transcript = answered.transcript if answered is not None else None
        system, user = model_answer_prompts(question, ctx.candidate, transcript)
        text = await deps.llm.complete_text(system=system, user=user)
        answers.append(ModelAnswer(question_id=question.id, answer=text))
    return answers


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
    )
