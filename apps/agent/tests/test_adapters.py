"""Offline tests for the deterministic mock adapters."""

import asyncio

from deepinterview_agent.core.adapters.mock import (
    MockEmbeddings,
    MockLLM,
    MockSearch,
    build_mock,
)
from deepinterview_agent.shared_models import (
    InterviewContext,
    QuestionPlan,
    ScoreCard,
)


def _run(coro):
    return asyncio.run(coro)


def test_build_mock_question_plan_is_valid() -> None:
    plan = build_mock(QuestionPlan)
    assert isinstance(plan, QuestionPlan)
    assert len(plan.questions) >= 1
    q = plan.questions[0]
    assert q.text["en"] == "mock"
    assert 1 <= q.difficulty <= 5
    assert len(q.rubric) >= 1
    assert len(q.followups) >= 1


def test_mock_llm_complete_json_schema_valid() -> None:
    plan = _run(MockLLM().complete_json(system="s", user="u", schema=QuestionPlan))
    assert isinstance(plan, QuestionPlan)

    ctx = _run(MockLLM().complete_json(system="s", user="u", schema=InterviewContext))
    assert isinstance(ctx, InterviewContext)
    # Defaulted fields stay at their defaults.
    assert ctx.cursor == 0
    assert ctx.answers == []
    assert ctx.scorecard is None

    sc = _run(MockLLM().complete_json(system="s", user="u", schema=ScoreCard))
    assert isinstance(sc, ScoreCard)
    assert sc.language_report.summary == "mock"


def test_mock_llm_complete_json_deterministic() -> None:
    a = _run(MockLLM().complete_json(system="s", user="u", schema=QuestionPlan))
    b = _run(MockLLM().complete_json(system="s", user="u", schema=QuestionPlan))
    assert a.model_dump() == b.model_dump()


def test_mock_llm_complete_text_is_str() -> None:
    text = _run(MockLLM().complete_text(system="s", user="u"))
    assert isinstance(text, str) and text


def test_mock_search_deterministic() -> None:
    a = _run(MockSearch().search("acme payments"))
    b = _run(MockSearch().search("acme payments"))
    assert [r.model_dump() for r in a] == [r.model_dump() for r in b]
    assert len(a) >= 1


def test_mock_embeddings_deterministic_and_dim() -> None:
    a = _run(MockEmbeddings().embed(["hello", "world"]))
    b = _run(MockEmbeddings().embed(["hello", "world"]))
    assert a == b
    assert len(a) == 2
    assert all(len(v) == MockEmbeddings.DIM for v in a)
    # Different text -> different vector.
    assert a[0] != a[1]
