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

from typing import TYPE_CHECKING

from ..shared_models import LanguageReport, ScoreCard
from .evaluator import evaluate
from .language_coach import coach
from .report import generate_report
from .verifier import verify_scores

if TYPE_CHECKING:
    from ..core.deps import Deps
    from ..shared_models import ScoreRequest

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
    )


async def run_score(req: ScoreRequest, deps: Deps) -> ScoreCard:
    """Score an interview session and return (and persist) its ``ScoreCard``."""
    ctx = await deps.repo.load_context(req.session_id)
    if ctx is None:
        # No context to score. Returning (rather than persisting) is correct for
        # both an unknown session (nothing to write) and a prep-errored session
        # (don't overwrite its "error" status with "complete").
        return _missing_context_scorecard(req.session_id)

    comp_scores = await evaluate(ctx, deps)
    if deps.settings.enable_score_verifier:
        comp_scores = await verify_scores(ctx, comp_scores, deps)
    lang_report = await coach(ctx, deps)
    scorecard = await generate_report(ctx, comp_scores, lang_report, deps)

    await deps.repo.save_scorecard(req.session_id, scorecard)
    await deps.repo.update_status(req.session_id, "complete")
    return scorecard
