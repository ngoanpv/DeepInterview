"""Offline tests for the WP-7 scoring pipeline (MockLLM / MemoryRepository).

These run ``run_prep`` to get a ready session, seed a couple of answers onto the
persisted ``InterviewContext``, then run ``run_score`` end-to-end with the
deterministic default adapters — no API keys, no network.

Note on seeding: answers are appended via ``load_context -> ctx.answers.append
-> save_context``, NOT ``repo.append_answer``. For ``MemoryRepository`` only the
``context`` blob is re-read by ``load_context``; ``append_answer`` writes to a
separate row field that scoring never sees, so it would silently score every
question as unanswered.
"""

from __future__ import annotations

import asyncio

from deepinterview_agent.core.deps import build_deps
from deepinterview_agent.post import run_score
from deepinterview_agent.prep import run_prep
from deepinterview_agent.shared_models import (
    AnswerRecord,
    InterviewContext,
    LanguageMode,
    PrepRequest,
    ScoreCard,
    ScoreRequest,
)


def _request(primary: str = "en", mixed: bool = False) -> PrepRequest:
    return PrepRequest(
        cv_url="https://example.com/cv.pdf",
        jd_text="Senior Backend Engineer building distributed payment systems in Python.",
        company="ExampleCorp",
        language_mode=LanguageMode(primary=primary, mixed=mixed),
    )


def _answer_for(question_id: str, n: int) -> AnswerRecord:
    return AnswerRecord(
        question_id=question_id,
        transcript=(
            f"Well, um, for question {n} I would start by clarifying the requirements, "
            "then I designed a service that, you know, handled retries and idempotency."
        ),
        started_at="2026-06-08T09:00:00Z",
        ended_at="2026-06-08T09:02:00Z",
        duration_sec=120.0,
    )


def _seed_answers(session_id: str, deps, count: int = 3) -> InterviewContext:
    """Append up to ``count`` answers (matching real plan question ids) and persist."""
    ctx = asyncio.run(deps.repo.load_context(session_id))
    assert ctx is not None
    questions = ctx.plan.questions
    assert questions, "prep should yield at least one planned question"
    for i, question in enumerate(questions[:count], start=1):
        ctx.answers.append(_answer_for(question.id, i))
    asyncio.run(deps.repo.save_context(session_id, ctx))
    return ctx


def _prepare_session(deps) -> tuple[str, InterviewContext]:
    session_id = asyncio.run(run_prep(_request(), deps))
    ctx = _seed_answers(session_id, deps)
    return session_id, ctx


def _assert_valid_scorecard(sc: ScoreCard, ctx: InterviewContext) -> None:
    assert isinstance(sc, ScoreCard)

    # competency_scores non-empty and every score within range.
    assert sc.competency_scores, "expected at least one competency score"
    for cs in sc.competency_scores:
        assert 0.0 <= cs.score <= 5.0, f"score {cs.score} out of 0..5"
        assert cs.level in {"weak", "developing", "solid", "strong"}

    # overall_score is a clamped mean.
    assert 0.0 <= sc.overall_score <= 5.0

    # Loop contract: every competency maps to a planned question's target_competency.
    plan_competencies = {q.target_competency for q in ctx.plan.questions}
    for cs in sc.competency_scores:
        assert cs.competency in plan_competencies, (
            f"competency {cs.competency!r} not in plan target_competencies"
        )

    # weak_competencies is a subset of the scored competencies.
    scored = {cs.competency for cs in sc.competency_scores}
    assert set(sc.weak_competencies) <= scored

    # A model answer per planned question.
    answered_ids = {ma.question_id for ma in sc.model_answers}
    assert answered_ids == {q.id for q in ctx.plan.questions}

    # Language report is well-formed.
    assert 0.0 <= sc.language_report.fluency_score <= 5.0
    assert 0.0 <= sc.language_report.clarity_score <= 5.0
    assert sc.language_report.filler_word_count >= 0


def test_run_score_produces_valid_scorecard() -> None:
    deps = build_deps()
    session_id, ctx = _prepare_session(deps)

    sc = asyncio.run(run_score(ScoreRequest(session_id=session_id), deps))

    _assert_valid_scorecard(sc, ctx)
    # Session was marked complete.
    assert deps.repo.get_status(session_id) == "complete"
    # The scorecard round-trips through validation.
    assert ScoreCard.model_validate(sc.model_dump()) == sc


def test_run_score_competencies_map_to_plan() -> None:
    deps = build_deps()
    session_id, ctx = _prepare_session(deps)

    sc = asyncio.run(run_score(ScoreRequest(session_id=session_id), deps))

    plan_competencies = {q.target_competency for q in ctx.plan.questions}
    assert plan_competencies, "plan must define target competencies"
    # Every scored competency is drawn from the plan (the Prep Coach loop contract).
    assert {cs.competency for cs in sc.competency_scores} <= plan_competencies
    # weak_competencies likewise stay inside the scored competency space.
    assert set(sc.weak_competencies) <= {cs.competency for cs in sc.competency_scores}


def test_run_score_is_stable_on_rerun() -> None:
    deps = build_deps()
    session_id, ctx = _prepare_session(deps)

    first = asyncio.run(run_score(ScoreRequest(session_id=session_id), deps))
    second = asyncio.run(run_score(ScoreRequest(session_id=session_id), deps))

    # Deterministic offline: identical structure and values across runs.
    assert first.model_dump() == second.model_dump()
    _assert_valid_scorecard(second, ctx)
    assert deps.repo.get_status(session_id) == "complete"


def test_run_score_handles_missing_context() -> None:
    deps = build_deps()
    # An unknown session has no persisted context -> a valid, empty error card.
    sc = asyncio.run(run_score(ScoreRequest(session_id="sess_does_not_exist"), deps))

    assert isinstance(sc, ScoreCard)
    assert sc.competency_scores == []
    assert sc.weak_competencies == []
    assert sc.overall_score == 0.0
    assert sc.coverage_pct == 0.0
    assert ScoreCard.model_validate(sc.model_dump()) == sc


def test_run_score_skips_when_no_answers() -> None:
    """A context that exists but has ZERO answers is flagged ``no_answers`` and
    NOT scored into a misleading all-zeros ``complete`` card (the root-cause fix)."""
    deps = build_deps()
    # run_prep yields a ready session with a plan but no answers seeded.
    session_id = asyncio.run(run_prep(_request(), deps))
    ctx = asyncio.run(deps.repo.load_context(session_id))
    assert ctx is not None and ctx.answers == []

    sc = asyncio.run(run_score(ScoreRequest(session_id=session_id), deps))

    # A well-formed empty card is returned (for the direct API caller)...
    assert isinstance(sc, ScoreCard)
    assert sc.competency_scores == []
    assert sc.overall_score == 0.0
    assert sc.coverage_pct == 0.0
    assert ScoreCard.model_validate(sc.model_dump()) == sc
    # ...but the session is flagged no_answers, NOT marked complete.
    assert deps.repo.get_status(session_id) == "no_answers"


def test_run_score_skips_when_all_answers_are_blank() -> None:
    """Answers whose transcripts are ALL empty/whitespace count as NO answers.

    The guard is ``not any((a.transcript or '').strip() ...)`` — NOT a bare
    ``if not ctx.answers``. A session whose only records are ``save_answer("")``
    calls (the model fired the tool with empty text, no recoverable speech)
    must land on ``no_answers`` with NO persisted scorecard, never flow into
    evaluate and ship a misleading all-zeros 'complete' card."""
    deps = build_deps()
    session_id = asyncio.run(run_prep(_request(), deps))
    ctx = asyncio.run(deps.repo.load_context(session_id))
    assert ctx is not None
    question_id = ctx.plan.questions[0].id
    for blank in ("", "   "):
        ctx.answers.append(
            AnswerRecord(
                question_id=question_id, transcript=blank, started_at="", ended_at=""
            )
        )
    asyncio.run(deps.repo.save_context(session_id, ctx))
    assert ctx.answers, "precondition: the answers list itself is non-empty"

    sc = asyncio.run(run_score(ScoreRequest(session_id=session_id), deps))

    # A well-formed empty card is returned for the direct caller...
    assert isinstance(sc, ScoreCard)
    assert sc.competency_scores == []
    assert sc.overall_score == 0.0
    assert sc.coverage_pct == 0.0
    # ...the session is flagged no_answers (NOT complete), nothing persisted.
    assert deps.repo.get_status(session_id) == "no_answers"
    assert deps.repo._rows[session_id].scorecard is None


def test_run_score_reports_partial_coverage() -> None:
    """Unanswered questions lower coverage_pct and never count as weak."""
    deps = build_deps()
    session_id, ctx = _prepare_session(deps)  # seeds 3 answers

    sc = asyncio.run(run_score(ScoreRequest(session_id=session_id), deps))

    answered_ids = {a.question_id for a in ctx.answers if a.transcript and a.transcript.strip()}
    total = len(ctx.plan.questions)
    expected = len(answered_ids) / total if total else 1.0
    assert abs(sc.coverage_pct - expected) < 1e-9

    # A competency we never probed must not appear as weak or even as a score.
    answered_comps = {q.target_competency for q in ctx.plan.questions if q.id in answered_ids}
    assert set(sc.weak_competencies) <= answered_comps
    assert {cs.competency for cs in sc.competency_scores} <= answered_comps


def test_run_score_errors_when_evaluate_stage_fails(monkeypatch) -> None:
    """Total evaluate failure must NOT persist a zero-score 'complete' card.

    Per-question failures are isolated inside ``evaluate``; if the WHOLE stage
    dies, an answered interview must not read as scoring 0.0. The session is
    marked errored (retriable — /api/score can re-run from the same context),
    a valid card is still returned, and nothing is persisted.
    """
    deps = build_deps()
    session_id, _ctx = _prepare_session(deps)

    import deepinterview_agent.post as post

    async def _boom(*args, **kwargs):
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(post, "evaluate", _boom)

    sc = asyncio.run(run_score(ScoreRequest(session_id=session_id), deps))

    assert isinstance(sc, ScoreCard)
    assert sc.competency_scores == []  # evaluation produced nothing
    assert ScoreCard.model_validate(sc.model_dump()) == sc
    assert deps.repo.get_status(session_id) == "error"
    assert deps.repo._rows[session_id].scorecard is None  # nothing persisted


def test_run_score_degrades_when_a_late_stage_fails(monkeypatch) -> None:
    """A failing NARRATIVE stage still yields a valid, persisted, COMPLETE card.

    Competency scores survived, so the card is persisted in degraded form
    (numbers kept, narrative empty) rather than discarded.
    """
    deps = build_deps()
    session_id, _ctx = _prepare_session(deps)

    import deepinterview_agent.post as post

    async def _boom(*args, **kwargs):
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(post, "generate_report", _boom)

    sc = asyncio.run(run_score(ScoreRequest(session_id=session_id), deps))

    assert isinstance(sc, ScoreCard)
    assert sc.competency_scores  # evaluated numbers preserved
    assert ScoreCard.model_validate(sc.model_dump()) == sc
    assert deps.repo.get_status(session_id) == "complete"
