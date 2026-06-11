"""End-to-end regression suite for the report feature at the API level.

The offline twin of the production flow ``prep -> live -> live-result -> score
-> session view``: a session is prepped with the deterministic adapters
(MockLLM / MockSearch / MemoryRepository — no keys, no network), the live
interview is simulated through the pure ``live.state`` machine (the worker's
livekit wrapper is NOT importable in the test venv), and the worker's shutdown
write-back is replayed verbatim over the FastAPI app: ``state.reconstruct_answers``
first (exactly as ``worker._on_shutdown`` does, BEFORE computing ``has_answers``),
then ``POST /api/session/{id}/live-result``, then ``POST /api/score``, then
``GET /api/session/{id}``.

The production bug pinned here: sessions with real speech landed on
``no_answers`` ("no report") whenever the live model never called the
``save_answer`` tool — everything the candidate said was silently dropped.
``state.add_turn`` now tags each transcript turn with the active question id and
``state.reconstruct_answers`` recovers those unsaved answers at shutdown, so the
report pipeline scores them like any saved answer.

Repo sharing: ``build_deps()`` (used inline by these tests, mirroring
``test_live._build_context``) and every API route resolve to the SAME cached
``Deps`` whose repo is the module-singleton ``MemoryRepository`` (conftest blanks
the Supabase creds), so a session prepped inline is visible to the TestClient
and vice versa — exactly the pattern ``test_app`` relies on.
"""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from deepinterview_agent.app import create_app
from deepinterview_agent.core.deps import Deps, build_deps
from deepinterview_agent.live import state
from deepinterview_agent.live.state import InterviewUserdata
from deepinterview_agent.prep import run_prep
from deepinterview_agent.shared_models import (
    LanguageMode,
    PrepRequest,
    ScoreCard,
)

# A substantive spoken answer (~50 words): comfortably above any thinness
# threshold and unambiguously "real speech" for the recovery scenarios.
_SPOKEN_ANSWER = (
    "I led the incident response when our payments ledger started double-charging "
    "customers. I traced the bug to a race between the retry worker and the "
    "settlement job, added an idempotency key on every write, backfilled the "
    "corrupted rows, and wrote a regression test so the failure mode can never "
    "silently return."
)

_CURATED_ANSWER = "The model's curated answer for question one."


def _client() -> TestClient:
    return TestClient(create_app())


def _prep_userdata() -> tuple[Deps, InterviewUserdata]:
    """Run the offline prep pipeline and wrap the ready context for the live sim."""
    deps = build_deps()
    req = PrepRequest(
        cv_url="https://example.com/cv.pdf",
        jd_text="Senior Backend Engineer building distributed payment systems in Python.",
        company="ExampleCorp",
        language_mode=LanguageMode(primary="en", mixed=False),
    )
    session_id = asyncio.run(run_prep(req, deps))
    ctx = asyncio.run(deps.repo.load_context(session_id))
    assert ctx is not None, "prep must yield a ready context"
    return deps, InterviewUserdata(ctx=ctx, session_id=ctx.session_id)


def _add_behavioral_question(ud: InterviewUserdata) -> None:
    """Augment the one-question mock plan with a second, different-section question."""
    first = ud.ctx.plan.questions[0]
    ud.ctx.plan.questions.append(
        first.model_copy(update={"id": "q_behavioral", "section": "behavioral"})
    )


def _post_live_result(
    client: TestClient, ud: InterviewUserdata, status: str | None = None
) -> None:
    """Replay the worker's shutdown write-back through the API (must 200)."""
    payload: dict = {
        "context": ud.ctx.model_dump(mode="json"),
        "transcript": ud.transcript,
        "status": status,
    }
    resp = client.post(f"/api/session/{ud.session_id}/live-result", json=payload)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True}


def _post_score(client: TestClient, session_id: str) -> dict:
    resp = client.post("/api/score", json={"session_id": session_id})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _get_view(client: TestClient, session_id: str) -> dict:
    resp = client.get(f"/api/session/{session_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _simulate_unsaved_interview(ud: InterviewUserdata) -> int:
    """Speak a real answer WITHOUT save_answer, then run the shutdown recovery.

    Mirrors worker._on_shutdown ordering: reconstruct_answers runs BEFORE any
    has_answers decision or persistence. Returns the recovered-record count.
    """
    state.add_turn(ud, "assistant", "Tell me about a hard production bug you fixed.")
    state.add_turn(ud, "user", _SPOKEN_ANSWER)
    assert ud.ctx.answers == [], "precondition: the model never called save_answer"
    return state.reconstruct_answers(ud)


def test_happy_path_saved_answers_yields_complete_view_with_scorecard() -> None:
    """prep -> save_answer + tagged turns -> live-result -> score -> view shows a
    'complete' session with a numeric scorecard and the answers preserved."""
    _deps, ud = _prep_userdata()
    client = _client()
    q1 = state.current_question(ud)
    assert q1 is not None

    # The live model behaved: it logged turns AND called the save_answer tool.
    state.add_turn(ud, "assistant", q1.text.get("en", "First question."))
    state.add_turn(ud, "user", _SPOKEN_ANSWER)
    state.save_answer(
        ud,
        transcript=_SPOKEN_ANSWER,
        started_at="2026-06-11T09:00:00Z",
        ended_at="2026-06-11T09:02:00Z",
    )

    _post_live_result(client, ud)
    _post_score(client, ud.session_id)

    view = _get_view(client, ud.session_id)
    assert view["status"] == "complete"
    sc = view["scorecard"]
    assert sc is not None
    assert isinstance(sc["overall_score"], (int, float))
    assert 0.0 <= sc["overall_score"] <= 5.0
    # The answers the worker pushed survive in the served context.
    answers = view["context"]["answers"]
    assert len(answers) == 1
    assert answers[0]["question_id"] == q1.id
    assert answers[0]["transcript"] == _SPOKEN_ANSWER


def test_recovery_when_save_answer_never_called_still_reaches_complete() -> None:
    """THE production bug: real speech but the model never called save_answer.

    reconstruct_answers must recover the spoken answer so the session scores to
    'complete' with a scorecard — NOT land on no_answers ("no report")."""
    _deps, ud = _prep_userdata()
    client = _client()
    q1 = state.current_question(ud)
    assert q1 is not None

    recovered = _simulate_unsaved_interview(ud)
    assert recovered == 1
    assert ud.ctx.answers[0].question_id == q1.id
    assert ud.ctx.answers[0].transcript == _SPOKEN_ANSWER

    # has_answers is now True -> the worker sends no terminal status hint.
    _post_live_result(client, ud)
    _post_score(client, ud.session_id)

    view = _get_view(client, ud.session_id)
    assert view["status"] == "complete"
    assert view["status"] != "no_answers"
    assert view["scorecard"] is not None
    assert view["scorecard"]["competency_scores"], "recovered answer must be scored"


def test_silent_call_stays_no_answers_and_score_does_not_fabricate() -> None:
    """A call with NO user speech ends honestly: status no_answers, no scorecard
    — and a later /api/score must not fabricate one or flip the status."""
    deps, ud = _prep_userdata()
    client = _client()

    state.add_turn(ud, "assistant", "Tell me about a hard production bug you fixed.")
    state.add_turn(ud, "assistant", "Hello? Are you still there?")
    assert state.reconstruct_answers(ud) == 0
    assert ud.ctx.answers == []

    # has_answers is False -> the worker sends the terminal no_answers hint.
    _post_live_result(client, ud, status="no_answers")

    view = _get_view(client, ud.session_id)
    assert view["status"] == "no_answers"
    assert view["scorecard"] is None

    # Scoring anyway (e.g. a manual retry) must not invent a report.
    body = _post_score(client, ud.session_id)
    assert body["scorecard"]["competency_scores"] == []
    assert body["scorecard"]["overall_score"] == 0.0

    view = _get_view(client, ud.session_id)
    assert view["status"] == "no_answers"
    assert view["scorecard"] is None
    assert deps.repo._rows[ud.session_id].scorecard is None  # nothing persisted


def test_mixed_saved_and_recovered_answers_score_and_curated_q1_wins() -> None:
    """Q1 saved via the tool, Q2 only spoken: recovery adds EXACTLY the Q2 record,
    never touches the curated Q1 one, and evaluator-style last-wins indexing
    still resolves Q1 to the curated text."""
    _deps, ud = _prep_userdata()
    _add_behavioral_question(ud)
    client = _client()
    q1 = state.current_question(ud)
    assert q1 is not None

    # Q1: raw STT turn PLUS a curated save_answer call from the model. The raw
    # speech clears the substance gate, so ONLY the qid-in-saved guard keeps
    # recovery from adding a second Q1 record.
    state.add_turn(ud, "assistant", "First question.")
    state.add_turn(
        ud, "user", "raw stt text for question one with enough words to clear the substance gate"
    )
    state.save_answer(ud, transcript=_CURATED_ANSWER, started_at="", ended_at="")
    state.advance(ud)  # -> q_behavioral

    # Q2: spoken only; the model forgot the tool.
    state.add_turn(ud, "assistant", "Now a behavioral question.")
    state.add_turn(ud, "user", _SPOKEN_ANSWER)

    recovered = state.reconstruct_answers(ud)
    assert recovered == 1
    assert len(ud.ctx.answers) == 2
    assert ud.ctx.answers[0].transcript == _CURATED_ANSWER  # untouched
    assert ud.ctx.answers[1].question_id == "q_behavioral"
    assert ud.ctx.answers[1].transcript == _SPOKEN_ANSWER

    # The evaluator indexes answers by question id, last record winning — Q1
    # must resolve to the CURATED text, not the raw STT turn.
    by_id = {a.question_id: a for a in ud.ctx.answers}
    assert by_id[q1.id].transcript == _CURATED_ANSWER

    _post_live_result(client, ud)
    _post_score(client, ud.session_id)

    view = _get_view(client, ud.session_id)
    assert view["status"] == "complete"
    sc = ScoreCard.model_validate(view["scorecard"])
    # Both questions count as answered: full coverage, a model answer for each.
    assert sc.coverage_pct == 1.0
    assert {ma.question_id for ma in sc.model_answers} == {q1.id, "q_behavioral"}


def test_tagged_transcript_roundtrips_through_live_result() -> None:
    """The question_id-tagged transcript persists VERBATIM through live-result,
    keeping the tags reconstruct_answers (and any future audit) depends on."""
    deps, ud = _prep_userdata()
    client = _client()
    q1 = state.current_question(ud)
    assert q1 is not None

    state.add_turn(ud, "assistant", "Tell me about a hard production bug you fixed.")
    state.add_turn(ud, "user", _SPOKEN_ANSWER)

    _post_live_result(client, ud)

    persisted = deps.repo._rows[ud.session_id].transcript
    assert persisted == ud.transcript
    assert all("question_id" in turn for turn in persisted)
    assert {turn["question_id"] for turn in persisted} == {q1.id}


def test_scoring_idempotent_after_recovery_returns_persisted_card() -> None:
    """A second /api/score after a recovered interview returns the SAME persisted
    card (no re-scoring, no overwrite) and the session stays 'complete'."""
    deps, ud = _prep_userdata()
    client = _client()

    assert _simulate_unsaved_interview(ud) == 1
    _post_live_result(client, ud)

    first = _post_score(client, ud.session_id)
    second = _post_score(client, ud.session_id)

    # Stable field AND the full card agree across calls.
    assert second["scorecard"]["summary"] == first["scorecard"]["summary"]
    assert second["scorecard"] == first["scorecard"]
    # The second response IS the persisted card, byte-for-byte as a model.
    persisted = ScoreCard.model_validate(deps.repo._rows[ud.session_id].scorecard)
    assert ScoreCard.model_validate(second["scorecard"]) == persisted
    assert _get_view(client, ud.session_id)["status"] == "complete"


def test_empty_saved_answer_does_not_block_recovery() -> None:
    """A save_answer call with a BLANK transcript must not count as 'saved':
    the spoken answer for the same question is still recovered and scored."""
    _deps, ud = _prep_userdata()
    client = _client()
    q1 = state.current_question(ud)
    assert q1 is not None

    # The model called the tool but passed an empty transcript...
    state.save_answer(ud, transcript="", started_at="", ended_at="")
    # ...while the candidate actually spoke a real answer to the same question.
    state.add_turn(ud, "user", _SPOKEN_ANSWER)

    recovered = state.reconstruct_answers(ud)
    assert recovered == 1, "blank saved record must not suppress recovery"
    assert ud.ctx.answers[-1].question_id == q1.id
    assert ud.ctx.answers[-1].transcript == _SPOKEN_ANSWER

    # Without recovery this session would have scored as no_answers.
    _post_live_result(client, ud)
    _post_score(client, ud.session_id)
    view = _get_view(client, ud.session_id)
    assert view["status"] == "complete"
    assert view["scorecard"] is not None


def test_live_result_disallowed_status_complete_is_ignored() -> None:
    """The live-result status hint is a CLOSED set ({no_answers, error} only):
    POSTing status='complete' must NOT flip the session to complete without a
    scorecard — the request succeeds but the hint is dropped, and the view
    still reads 'ready' with no scorecard. A refactor to a bare
    ``if req.status: update_status(req.status)`` regresses exactly this."""
    deps, ud = _prep_userdata()
    client = _client()
    state.add_turn(ud, "user", _SPOKEN_ANSWER)

    _post_live_result(client, ud, status="complete")  # asserts the 200 + ok body

    view = _get_view(client, ud.session_id)
    assert view["status"] == "ready", "disallowed hint must leave the status alone"
    assert view["scorecard"] is None
    assert deps.repo.get_status(ud.session_id) == "ready"  # nothing hit the store


def test_live_result_garbage_status_is_not_persisted_and_view_stays_readable() -> None:
    """A garbage status must never be written: ``SessionView.status`` is a
    Literal, so persisting it would make EVERY later ``GET /api/session/{id}``
    raise ValidationError (500) — the failure class views.py warns about. The
    write must be ignored and the subsequent GET must still 200."""
    deps, ud = _prep_userdata()
    client = _client()

    _post_live_result(client, ud, status="garbage")

    view = _get_view(client, ud.session_id)  # _get_view asserts the GET 200s
    assert view["status"] == "ready"
    assert deps.repo.get_status(ud.session_id) == "ready"
    # The context write-back itself still landed (only the status was dropped).
    assert view["context"] is not None


def test_recovered_answer_reaches_report_as_answered_coverage() -> None:
    """The recovered question id reads as ANSWERED in the report itself: full
    coverage_pct, a model answer for it, and competencies drawn from the plan."""
    _deps, ud = _prep_userdata()
    client = _client()
    q1 = state.current_question(ud)
    assert q1 is not None

    assert _simulate_unsaved_interview(ud) == 1
    _post_live_result(client, ud)
    _post_score(client, ud.session_id)

    view = _get_view(client, ud.session_id)
    assert view["status"] == "complete"
    sc = ScoreCard.model_validate(view["scorecard"])

    # The single-question mock plan was fully covered by the RECOVERED answer.
    assert sc.coverage_pct == 1.0
    assert {ma.question_id for ma in sc.model_answers} == {q1.id}
    # The recovered answer produced real competency scores mapped to the plan.
    plan_competencies = {q.target_competency for q in ud.ctx.plan.questions}
    assert sc.competency_scores
    assert {cs.competency for cs in sc.competency_scores} <= plan_competencies
