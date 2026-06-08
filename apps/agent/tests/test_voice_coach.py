"""Offline tests for the livekit-free spoken Study Coach helpers.

These exercise ONLY the livekit-free logic: the Socratic instructions builder
(``coach.prompts.coach_agent_instructions``) and the weak-areas summary helper
(``live.state.weak_areas_summary``). They deliberately do NOT import
``live.coach_agent`` or ``worker_coach`` (both require the livekit extra). The
CoachAgent persona + worker entrypoint are integration-tested manually.
"""

from __future__ import annotations

from deepinterview_agent.coach.prompts import coach_agent_instructions
from deepinterview_agent.live.state import weak_areas_summary
from deepinterview_agent.shared_models import (
    CompetencyScore,
    LanguageReport,
    ScoreCard,
)


def _scorecard(weak: list[str]) -> ScoreCard:
    comp = [
        CompetencyScore(
            competency=c, score=1.5, evidence=f"Struggled with {c}.", level="weak"
        )
        for c in weak
    ]
    return ScoreCard(
        overall_score=1.5,
        competency_scores=comp,
        strengths=[],
        weaknesses=list(weak),
        weak_competencies=list(weak),
        model_answers=[],
        next_steps=[],
        language_report=LanguageReport(
            fluency_score=3.0,
            filler_word_count=2,
            clarity_score=3.0,
            code_switching_notes="",
            pronunciation_notes="",
            summary="ok",
        ),
        summary="test scorecard",
    )


def test_instructions_are_socratic_and_localized() -> None:
    text = coach_agent_instructions("Weak areas: System Design.", "vi")
    assert isinstance(text, str) and text
    # Mentions the injected weak-areas context verbatim and the language.
    assert "System Design" in text
    assert "vi" in text
    # Socratic intent: never just lecture / hand over the answer.
    assert "question" in text.lower()


def test_weak_areas_summary_lists_weak_competencies() -> None:
    summary = weak_areas_summary(_scorecard(["System Design", "Leadership"]))
    assert "System Design" in summary
    assert "Leadership" in summary


def test_weak_areas_summary_handles_no_scorecard() -> None:
    # A session that hasn't been scored yet must still yield a usable, non-empty line.
    summary = weak_areas_summary(None)
    assert isinstance(summary, str) and summary


def test_weak_areas_summary_handles_no_weak() -> None:
    summary = weak_areas_summary(_scorecard([]))
    assert isinstance(summary, str) and summary
