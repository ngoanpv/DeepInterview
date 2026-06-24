"""Offline tests for the WP-4 Study Coach (MockLLM / MockKnowledge).

run_coach_plan is a pure function of a ScoreCard; run_coach_chat grounds via the
default MockKnowledge client. No keys, no network.
"""

from __future__ import annotations

import asyncio

from deepinterview_agent.coach import run_coach_chat, run_coach_plan
from deepinterview_agent.core.deps import build_deps
from deepinterview_agent.shared_models import (
    Citation,
    CoachChatRequest,
    CompetencyScore,
    LanguageReport,
    ScoreCard,
    StudyPlan,
)


def _scorecard(weak: list[str]) -> ScoreCard:
    comp = [
        CompetencyScore(
            competency=c, score=1.5, evidence=f"Struggled with {c} under follow-up.", level="weak"
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


def test_coach_plan_covers_weak_competencies() -> None:
    deps = build_deps()
    sc = _scorecard(["System Design", "Leadership"])

    plan = asyncio.run(run_coach_plan(sc, deps))

    # One module per weak competency, mapping back onto the loop's competency space.
    assert {m.competency for m in plan.modules} == {"System Design", "Leadership"}
    assert plan.total_min == sum(m.est_min for m in plan.modules)
    for m in plan.modules:
        assert m.est_min >= 5
        assert m.status in {"unseen", "learning", "shaky", "mastered"}
    # Round-trips through validation.
    assert StudyPlan.model_validate(plan.model_dump()) == plan


def test_coach_plan_empty_when_no_weak() -> None:
    deps = build_deps()
    plan = asyncio.run(run_coach_plan(_scorecard([]), deps))
    assert plan.modules == []
    assert plan.total_min == 0
    assert plan.summary  # a non-empty, encouraging message


def test_coach_chat_returns_grounded_reply() -> None:
    deps = build_deps()
    req = CoachChatRequest(
        session_id="sess_x", query="How do I structure a STAR answer?", lang="en"
    )

    reply = asyncio.run(run_coach_chat(req, deps))

    assert isinstance(reply.answer, str) and reply.answer
    # No real KB configured (default) -> ungrounded + honest: NO fabricated sources.
    assert reply.citations == []
    assert len(reply.follow_ups) <= 3


def test_coach_chat_grounds_when_backend_configured() -> None:
    """With a real KB configured (LIGHTRAG_URL) the coach grounds + returns citations."""
    deps = build_deps()
    original = deps.settings.lightrag_url

    class _FakeKnowledge:
        async def search(self, user_id: str, query: str, lang: str):
            return ("Grounded context.", [Citation(title="Prep notes", url="kb://x", snippet="s")])

    deps.settings.lightrag_url = "http://localhost:9621"
    original_knowledge = deps.knowledge
    deps.knowledge = _FakeKnowledge()
    try:
        req = CoachChatRequest(session_id="sess_x", query="What is exactly-once?", lang="en")
        reply = asyncio.run(run_coach_chat(req, deps))
        assert len(reply.citations) >= 1
    finally:
        # Restore BOTH mutated fields on the shared cached deps — leaving the
        # _FakeKnowledge in place pollutes later tests (e.g. /api/kb/ingest now
        # calls deps.knowledge.ingest, which this double doesn't implement).
        deps.settings.lightrag_url = original
        deps.knowledge = original_knowledge
