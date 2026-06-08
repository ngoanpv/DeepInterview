"""Competency evaluation for the WP-7 scoring pipeline.

For every planned question we score the candidate's matching answer against the
question's rubric, producing one :class:`CompetencyScore`. Two things are pinned
deterministically rather than trusted to the model, because they carry the
loop contract:

* ``competency`` is forced to the question's ``target_competency`` (so the
  scorecard's competencies map back onto the plan and, downstream, onto the
  Prep Coach's shared entity space).
* ``level`` is derived from the numeric ``score`` via :func:`level_for_score`,
  so the band always agrees with the number.

When several questions share one ``target_competency`` their scores are merged
by averaging, and the merged band is re-derived from the averaged score.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..shared_models import CompetencyScore, MasteryLevel
from .prompts import evaluate_answer_prompts

if TYPE_CHECKING:
    from ..core.deps import Deps
    from ..shared_models import AnswerRecord, InterviewContext, PlannedQuestion


def _clamp_score(value: float) -> float:
    """Clamp a raw score into the documented 0-5 range."""
    return max(0.0, min(5.0, float(value)))


def level_for_score(score: float) -> MasteryLevel:
    """Map a 0-5 score onto a mastery band (>=4 strong, >=3 solid, >=2 developing)."""
    if score >= 4.0:
        return "strong"
    if score >= 3.0:
        return "solid"
    if score >= 2.0:
        return "developing"
    return "weak"


def _answers_by_question(ctx: InterviewContext) -> dict[str, AnswerRecord]:
    """Index answers by ``question_id`` (last answer wins on duplicates)."""
    return {a.question_id: a for a in ctx.answers}


async def _score_question(
    question: PlannedQuestion,
    answer: AnswerRecord | None,
    deps: Deps,
) -> CompetencyScore:
    """Score a single question, forcing competency + deriving level deterministically."""
    transcript = answer.transcript if answer is not None else None
    system, user = evaluate_answer_prompts(question, transcript)
    raw = await deps.llm.complete_json(system=system, user=user, schema=CompetencyScore)

    score = _clamp_score(raw.score)
    if answer is None:
        # No answer to ground a score: pin low with explicit, non-evidence text.
        score = 0.0
        evidence = "No answer was recorded for this question."
    else:
        evidence = raw.evidence or "Scored against the question rubric."

    return CompetencyScore(
        competency=question.target_competency,
        score=score,
        evidence=evidence,
        level=level_for_score(score),
    )


def _merge_by_competency(scores: list[CompetencyScore]) -> list[CompetencyScore]:
    """De-dup competencies by averaging their scores; preserve first-seen order."""
    order: list[str] = []
    buckets: dict[str, list[CompetencyScore]] = {}
    for cs in scores:
        if cs.competency not in buckets:
            buckets[cs.competency] = []
            order.append(cs.competency)
        buckets[cs.competency].append(cs)

    merged: list[CompetencyScore] = []
    for competency in order:
        group = buckets[competency]
        if len(group) == 1:
            merged.append(group[0])
            continue
        avg = _clamp_score(sum(cs.score for cs in group) / len(group))
        evidence = " ".join(cs.evidence for cs in group if cs.evidence).strip()
        merged.append(
            CompetencyScore(
                competency=competency,
                score=avg,
                evidence=evidence or "Averaged across multiple questions.",
                level=level_for_score(avg),
            )
        )
    return merged


async def evaluate(ctx: InterviewContext, deps: Deps) -> list[CompetencyScore]:
    """Score every planned question and return de-duplicated competency scores.

    Each ``CompetencyScore.competency`` equals the corresponding question's
    ``target_competency`` — the mapping the report and the Prep Coach loop rely
    on. Questions without a matching answer are scored low with non-evidence
    text rather than dropped.
    """
    by_question = _answers_by_question(ctx)
    raw_scores: list[CompetencyScore] = []
    for question in ctx.plan.questions:
        answer = by_question.get(question.id)
        raw_scores.append(await _score_question(question, answer, deps))
    return _merge_by_competency(raw_scores)
