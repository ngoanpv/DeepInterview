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

import asyncio
from typing import TYPE_CHECKING

from ..core.logging import get_logger
from ..shared_models import CompetencyScore, MasteryLevel
from .prompts import evaluate_answer_prompts

if TYPE_CHECKING:
    from ..core.deps import Deps
    from ..shared_models import AnswerRecord, InterviewContext, PlannedQuestion

log = get_logger(__name__)

# Bound concurrent per-question LLM calls: parallel enough to fit the stage
# timeout on long interviews, small enough to stay under provider rate limits.
_MAX_CONCURRENT_SCORING = 4


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
    answer: AnswerRecord,
    deps: Deps,
) -> CompetencyScore:
    """Score a single answered question, forcing competency + deriving level.

    Unanswered questions never reach here — ``evaluate`` skips them (a
    competency we never probed must not read as weak; see its docstring).
    """
    system, user = evaluate_answer_prompts(question, answer.transcript)
    raw = await deps.llm.complete_json(system=system, user=user, schema=CompetencyScore)

    score = _clamp_score(raw.score)
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
    on. Questions that were never answered (no record, or an empty transcript)
    are SKIPPED rather than scored ``0.0``: a competency we never probed must
    not read as a weak one (that would poison ``overall_score`` and tell the
    Prep Coach to teach something the interview simply didn't reach). The
    fraction actually covered is reported separately as ``ScoreCard.coverage_pct``.

    Per-question failures are ISOLATED: one failed/malformed LLM call drops that
    question's score (logged) instead of wiping the whole stage — a transient
    provider error on question 7 must not discard questions 1-6. Calls run
    concurrently (bounded) so long interviews fit inside the stage timeout.
    """
    by_question = _answers_by_question(ctx)
    answered = [
        (question, by_question[question.id])
        for question in ctx.plan.questions
        if question.id in by_question
        and (by_question[question.id].transcript or "").strip()
    ]

    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_SCORING)

    async def _score_one(question: PlannedQuestion, answer: AnswerRecord) -> CompetencyScore | None:
        async with semaphore:
            try:
                return await _score_question(question, answer, deps)
            except Exception:  # noqa: BLE001 - isolate: one bad call must not void the rest
                log.exception("evaluator: scoring failed for question %s; skipping", question.id)
                return None

    results = await asyncio.gather(*(_score_one(q, a) for q, a in answered))
    raw_scores = [r for r in results if r is not None]
    if answered and not raw_scores:
        # Every per-question call failed — that is a stage failure, not a
        # legitimately empty result; raise so run_score's guard degrades instead
        # of persisting a zero-score "complete" card for an answered interview.
        raise RuntimeError("evaluator: all per-question scoring calls failed")
    return _merge_by_competency(raw_scores)
