"""Offline tests for the in-memory session repository."""

import asyncio

from deepinterview_agent.core.adapters.mock import build_mock
from deepinterview_agent.core.persistence.repository import MemoryRepository
from deepinterview_agent.shared_models import (
    AnswerRecord,
    InterviewContext,
    LanguageMode,
    PrepRequest,
    ScoreCard,
)


def _run(coro):
    return asyncio.run(coro)


def _prep_request() -> PrepRequest:
    return PrepRequest(
        cv_url="https://example.com/cv.pdf",
        jd_text="We are hiring a backend engineer.",
        company="Acme Payments",
        language_mode=LanguageMode(primary="en", mixed=False),
    )


def test_create_save_load_round_trip() -> None:
    repo = MemoryRepository()
    session_id = _run(repo.create_session(_prep_request()))
    assert session_id.startswith("sess_")
    assert repo.get_status(session_id) == "prep"

    ctx = build_mock(InterviewContext)
    assert isinstance(ctx, InterviewContext)
    _run(repo.save_context(session_id, ctx))

    loaded = _run(repo.load_context(session_id))
    assert loaded is not None
    assert loaded.model_dump() == ctx.model_dump()


def test_update_status_and_missing_load() -> None:
    repo = MemoryRepository()
    session_id = _run(repo.create_session(_prep_request()))
    _run(repo.update_status(session_id, "ready"))
    assert repo.get_status(session_id) == "ready"
    # A session with no saved context returns None.
    assert _run(repo.load_context("sess_does_not_exist")) is None


def test_append_answer_and_save_scorecard() -> None:
    repo = MemoryRepository()
    session_id = _run(repo.create_session(_prep_request()))

    answer = AnswerRecord(
        question_id="q1",
        transcript="A mock answer.",
        started_at="2026-06-08T09:00:00Z",
        ended_at="2026-06-08T09:01:00Z",
    )
    _run(repo.append_answer(session_id, answer))

    scorecard = build_mock(ScoreCard)
    assert isinstance(scorecard, ScoreCard)
    _run(repo.save_scorecard(session_id, scorecard))

    _run(repo.save_transcript(session_id, [{"role": "agent", "text": "hi"}]))
