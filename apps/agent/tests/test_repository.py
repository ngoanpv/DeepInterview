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


def test_create_session_stamps_user_id() -> None:
    """Regression (report RLS bug, PR #5): the owning user must land on the row.

    Dropping the ``user_id=req.user_id`` stamp would silently pass the rest of
    the suite while breaking the hosted layer's RLS ownership read
    (``auth.uid() = user_id`` in supabase/migrations/0001_init.sql).
    """
    repo = MemoryRepository()
    owner = "11111111-2222-3333-4444-555555555555"
    req = _prep_request().model_copy(update={"user_id": owner})
    session_id = _run(repo.create_session(req))
    assert repo._rows[session_id].user_id == owner

    # The offline/no-auth path stays ownerless (None), never an empty string.
    anon_id = _run(repo.create_session(_prep_request()))
    assert repo._rows[anon_id].user_id is None


def test_save_coach_transcript_does_not_touch_interview_transcript() -> None:
    """The spoken coach's log persists separately from the interview record."""
    repo = MemoryRepository()
    session_id = _run(repo.create_session(_prep_request()))
    interview = [{"role": "user", "text": "my interview answer"}]
    coach = [{"role": "assistant", "text": "let's drill system design"}]
    _run(repo.save_transcript(session_id, interview))
    _run(repo.save_coach_transcript(session_id, coach))
    row = repo._rows[session_id]
    assert row.transcript == interview
    assert row.coach_transcript == coach


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
