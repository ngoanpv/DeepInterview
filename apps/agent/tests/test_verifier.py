"""Offline tests for the gated post/ adversarial score verifier (MockLLM).

The verifier is OFF by default; these tests turn it ON via an explicit
``Settings(enable_score_verifier=True)`` passed to ``build_deps`` -- deliberately
NOT by mutating ``deps.settings``, because ``get_settings()`` is ``@lru_cache``'d
and that singleton is shared with the other test modules. Seeding mirrors
``test_score.py`` (append answers via load->append->save_context). No keys, no
network.
"""

from __future__ import annotations

import asyncio

from deepinterview_agent.core.config import Settings
from deepinterview_agent.core.deps import build_deps
from deepinterview_agent.post import run_score, verify_scores
from deepinterview_agent.post.evaluator import evaluate, level_for_score
from deepinterview_agent.prep import run_prep
from deepinterview_agent.shared_models import (
    AnswerRecord,
    CompetencyScore,
    InterviewContext,
    LanguageMode,
    PrepRequest,
    ScoreCard,
    ScoreRequest,
)


def _request() -> PrepRequest:
    return PrepRequest(
        cv_url="https://example.com/cv.pdf",
        jd_text="Senior Backend Engineer building distributed payment systems in Python.",
        company="ExampleCorp",
        language_mode=LanguageMode(primary="en", mixed=False),
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
    ctx = asyncio.run(deps.repo.load_context(session_id))
    assert ctx is not None
    questions = ctx.plan.questions
    assert questions, "prep should yield at least one planned question"
    for i, question in enumerate(questions[:count], start=1):
        ctx.answers.append(_answer_for(question.id, i))
    asyncio.run(deps.repo.save_context(session_id, ctx))
    return ctx


def _deps_with_verifier(enabled: bool):
    """Fresh Deps with the verifier flag set explicitly (never touches the cache)."""
    return build_deps(Settings(enable_score_verifier=enabled))


def _prepare(deps) -> tuple[str, InterviewContext]:
    session_id = asyncio.run(run_prep(_request(), deps))
    ctx = _seed_answers(session_id, deps)
    return session_id, ctx


def _assert_scores_consistent(scores: list[CompetencyScore]) -> None:
    assert scores, "expected at least one competency score"
    for cs in scores:
        assert 0.0 <= cs.score <= 5.0, f"score {cs.score} out of 0..5"
        # Level always agrees with the (possibly adjusted) numeric score.
        assert cs.level == level_for_score(cs.score)
        assert cs.level in {"weak", "developing", "solid", "strong"}


def test_verify_scores_keeps_scores_in_range_and_levels_agree() -> None:
    deps = _deps_with_verifier(True)
    _, ctx = _prepare(deps)

    base = asyncio.run(evaluate(ctx, deps))
    verified = asyncio.run(verify_scores(ctx, base, deps))

    # Same competencies, same order; every score valid and band re-derived.
    assert [cs.competency for cs in verified] == [cs.competency for cs in base]
    _assert_scores_consistent(verified)


def test_verify_scores_is_deterministic_and_never_raises() -> None:
    deps = _deps_with_verifier(True)
    _, ctx = _prepare(deps)

    base = asyncio.run(evaluate(ctx, deps))
    first = asyncio.run(verify_scores(ctx, base, deps))
    second = asyncio.run(verify_scores(ctx, base, deps))

    assert [cs.model_dump() for cs in first] == [cs.model_dump() for cs in second]


def test_run_score_with_verifier_on_produces_valid_scorecard() -> None:
    deps = _deps_with_verifier(True)
    session_id, _ = _prepare(deps)

    sc = asyncio.run(run_score(ScoreRequest(session_id=session_id), deps))

    assert isinstance(sc, ScoreCard)
    assert 0.0 <= sc.overall_score <= 5.0
    _assert_scores_consistent(sc.competency_scores)
    # weak_competencies stay inside the scored competency space.
    scored = {cs.competency for cs in sc.competency_scores}
    assert set(sc.weak_competencies) <= scored
    assert ScoreCard.model_validate(sc.model_dump()) == sc
    assert deps.repo.get_status(session_id) == "complete"


def test_run_score_with_verifier_on_is_stable_on_rerun() -> None:
    deps = _deps_with_verifier(True)
    session_id, _ = _prepare(deps)

    first = asyncio.run(run_score(ScoreRequest(session_id=session_id), deps))
    second = asyncio.run(run_score(ScoreRequest(session_id=session_id), deps))

    assert first.model_dump() == second.model_dump()


def test_verifier_off_is_a_noop() -> None:
    """With the flag OFF, run_score equals a separate flag-off run (no verifier effect)."""
    deps_off_a = _deps_with_verifier(False)
    session_a, _ = _prepare(deps_off_a)
    sc_off = asyncio.run(run_score(ScoreRequest(session_id=session_a), deps_off_a))

    # Direct evaluate() (no verifier) and the flag-off run agree on the scores.
    ctx = asyncio.run(deps_off_a.repo.load_context(session_a))
    assert ctx is not None
    base = asyncio.run(evaluate(ctx, deps_off_a))
    assert [cs.model_dump() for cs in sc_off.competency_scores] == [
        cs.model_dump() for cs in base
    ]
