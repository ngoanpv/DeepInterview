"""WP-7 post / scoring pipeline.

Turns a completed interview (a persisted ``InterviewContext`` with answers) into
a ``ScoreCard`` and persists it. The post phase is latency-tolerant, so this is a
plain sequential pipeline (no LangGraph): evaluate competencies → assess spoken
language → assemble the report.

Public entry point — the stable contract the API layer and tests depend on::

    async def run_score(req: ScoreRequest, deps: Deps) -> ScoreCard

``run_score`` loads the context, scores it, persists the scorecard, marks the
session ``complete``, and returns the card. If the context is missing it returns
a well-formed *error* ``ScoreCard`` (without persisting and without raising) so
the API can always respond with a valid body and an errored session keeps its
status.

The loop contract: each ``CompetencyScore.competency`` equals some planned
question's ``target_competency``, and ``weak_competencies`` (the weak/developing
subset) is what the Prep Coach consumes to choose what to teach next.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from ..core.logging import get_logger
from ..shared_models import LanguageReport, ScoreCard
from .evaluator import evaluate
from .language_coach import coach
from .report import (
    _coverage_pct,
    _overall_score,
    _weak_competencies,
    generate_report,
)
from .verifier import verify_scores

if TYPE_CHECKING:
    from ..core.deps import Deps
    from ..shared_models import CompetencyScore, InterviewContext, ScoreRequest

log = get_logger(__name__)

__all__ = ["run_score", "evaluate", "coach", "generate_report", "verify_scores"]


def _missing_context_scorecard(session_id: str) -> ScoreCard:
    """A valid, empty scorecard for a session whose context cannot be loaded."""
    return ScoreCard(
        overall_score=0.0,
        competency_scores=[],
        strengths=[],
        weaknesses=[],
        weak_competencies=[],
        model_answers=[],
        next_steps=[],
        language_report=LanguageReport(
            fluency_score=0.0,
            filler_word_count=0,
            clarity_score=0.0,
            code_switching_notes="",
            pronunciation_notes="",
            summary="No interview context was found for this session.",
        ),
        summary=f"No interview context was found for session {session_id}; nothing to score.",
        coverage_pct=0.0,
    )


def _no_answers_scorecard(session_id: str) -> ScoreCard:
    """A valid, empty scorecard for a session that has a context but NO answers.

    Returned (not persisted) so a direct ``/api/score`` caller always gets a
    well-formed body. The session is flagged ``no_answers`` instead of
    ``complete`` so the report can show an honest empty state rather than a
    misleading all-zeros card.
    """
    return ScoreCard(
        overall_score=0.0,
        competency_scores=[],
        strengths=[],
        weaknesses=[],
        weak_competencies=[],
        model_answers=[],
        next_steps=[],
        language_report=LanguageReport(
            fluency_score=0.0,
            filler_word_count=0,
            clarity_score=0.0,
            code_switching_notes="",
            pronunciation_notes="",
            summary="No answers were recorded for this interview.",
        ),
        summary=(
            f"No answers were recorded for session {session_id}; "
            "the interview ended before any question was answered."
        ),
        coverage_pct=0.0,
    )


def _fallback_language_report() -> LanguageReport:
    """Neutral, well-formed language report used when the coach stage fails."""
    return LanguageReport(
        fluency_score=0.0,
        filler_word_count=0,
        clarity_score=0.0,
        code_switching_notes="",
        pronunciation_notes="",
        summary="Spoken-language assessment was unavailable for this interview.",
    )


def _degraded_scorecard(
    ctx: InterviewContext,
    comp_scores: list[CompetencyScore],
    lang_report: LanguageReport,
) -> ScoreCard:
    """A valid ScoreCard assembled WITHOUT the LLM narrative.

    Used when report generation (the narrative + model-answer LLM calls) fails
    but competency scoring and/or the language report succeeded. Preserves the
    numbers already computed so a transient model error never discards a
    completed interview's work.
    """
    return ScoreCard(
        overall_score=_overall_score(comp_scores),
        competency_scores=comp_scores,
        strengths=[],
        weaknesses=[],
        weak_competencies=_weak_competencies(comp_scores),
        model_answers=[],
        next_steps=["Re-run scoring to generate the full written report."],
        language_report=lang_report,
        summary=(
            "Partial scorecard: detailed report generation was temporarily "
            "unavailable. Competency scores are preserved; re-run scoring for "
            "the full narrative and model answers."
        ),
        coverage_pct=_coverage_pct(ctx),
    )


async def _guarded(coro, *, label: str, timeout: float):
    """Await ``coro`` with a timeout; on ANY error return ``None`` to fall back.

    The scoring pipeline is latency-tolerant but must never let one transient
    provider error or hang destroy a completed interview's scorecard.
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except Exception:  # noqa: BLE001 - degrade, never propagate, on the scoring path
        log.exception("post: scoring stage %r failed; degrading", label)
        return None


async def _maybe_distill_skill(session_id: str, deps: Deps) -> None:
    """Best-effort closed-loop step (WP-10): propose a reusable playbook delta.

    Gated behind ``settings.enable_skill_distiller`` (OFF by default). Writes a
    draft into the review queue only — never the live library, never the score
    response. Any failure is logged and swallowed.
    """
    if not deps.settings.enable_skill_distiller:
        return
    try:
        from ..skilllib.distiller import propose_skill  # noqa: PLC0415 - keep skilllib off the import hot path

        draft = await propose_skill(session_id, deps)
        log.info("post: skill distiller proposed draft %s for session %s", draft.id, session_id)
    except Exception:  # noqa: BLE001 - distiller is best-effort; must not affect scoring
        log.exception("post: skill distiller failed for session %s", session_id)


async def run_score(req: ScoreRequest, deps: Deps) -> ScoreCard:
    """Score an interview session and return (and persist) its ``ScoreCard``.

    Each stage (evaluate / coach / report) is individually guarded with a
    timeout and a structured fallback, so a transient provider failure degrades
    the scorecard rather than raising (which would 500 the API and leave the
    session stuck mid-scoring). Whenever a context exists the resulting card is
    persisted and the session is marked ``complete``.
    """
    ctx = await deps.repo.load_context(req.session_id)
    if ctx is None:
        # No context to score. Returning (rather than persisting) is correct for
        # both an unknown session (nothing to write) and a prep-errored session
        # (don't overwrite its "error" status with "complete").
        return _missing_context_scorecard(req.session_id)

    if not ctx.answers:
        # A context exists but no answers were captured (interview ended before
        # any question was answered, or answers never persisted). Do NOT run the
        # LLM scoring stages or mark the session "complete" with a blank card —
        # that yields a misleading all-zeros report. Flag it "no_answers" so the
        # UI shows an honest empty state, and persist NO scorecard.
        log.info("post: session %s has no answers; skipping scoring (no_answers)", req.session_id)
        await deps.repo.update_status(req.session_id, "no_answers")
        return _no_answers_scorecard(req.session_id)

    timeout = deps.settings.score_stage_timeout_sec

    comp_scores = await _guarded(evaluate(ctx, deps), label="evaluate", timeout=timeout)
    if comp_scores is None:
        comp_scores = []

    # Optional adversarial calibration pass (gated, OFF by default). Guarded so a
    # verifier failure leaves the evaluated scores untouched rather than degrading.
    if deps.settings.enable_score_verifier:
        verified = await _guarded(
            verify_scores(ctx, comp_scores, deps), label="verify", timeout=timeout
        )
        if verified is not None:
            comp_scores = verified

    lang_report = await _guarded(coach(ctx, deps), label="coach", timeout=timeout)
    if lang_report is None:
        lang_report = _fallback_language_report()

    scorecard = await _guarded(
        generate_report(ctx, comp_scores, lang_report, deps),
        label="generate_report",
        timeout=timeout,
    )
    if scorecard is None:
        scorecard = _degraded_scorecard(ctx, comp_scores, lang_report)

    await deps.repo.save_scorecard(req.session_id, scorecard)
    await deps.repo.update_status(req.session_id, "complete")

    # Closed-loop (WP-10): propose a reusable playbook delta. Off by default,
    # best-effort, and fully guarded so it can never affect the returned card.
    await _maybe_distill_skill(req.session_id, deps)

    return scorecard
