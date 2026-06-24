"""Regression tests for the real-LLM JSON response parser (no SDK / API key).

Pins the production bug found by the full-stack real-provider e2e: the question
planner — the largest schema, so the biggest real Gemini response — returned a
valid JSON object FOLLOWED BY extra data, which the old ``json.loads`` + greedy
``{.*}`` fallback rejected, silently falling back to the generic mock plan (every
interview asked one question titled "mock"). These tests run on the deterministic
mock plan shape, so they catch a regression in CI without any provider key.
"""

from __future__ import annotations

from deepinterview_agent.core.adapters.llm import _loads_json
from deepinterview_agent.core.adapters.mock import build_mock
from deepinterview_agent.shared_models import QuestionPlan


def test_loads_clean_object() -> None:
    assert _loads_json('{"a": 1}') == {"a": 1}


def test_loads_clean_array() -> None:
    assert _loads_json('[1, 2, 3]') == [1, 2, 3]


def test_loads_strips_json_fence() -> None:
    assert _loads_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _loads_json('```\n{"a": 1}\n```') == {"a": 1}


def test_loads_first_value_when_trailing_extra_data() -> None:
    """THE failure class: a complete object, then 'Extra data' json.loads rejects."""
    assert _loads_json('{"a": 1}\n{"b": 2}') == {"a": 1}
    assert _loads_json('{"a": 1}\n\nNote: hope this helps!') == {"a": 1}


def test_loads_object_after_leading_prose() -> None:
    assert _loads_json('Here is your JSON:\n{"a": 1}') == {"a": 1}


def test_question_plan_survives_trailing_extra_data() -> None:
    """A realistic QuestionPlan payload with a duplicate trailing object still
    validates to the FIRST (complete) plan — not a mock fallback."""
    plan = build_mock(QuestionPlan)
    payload = plan.model_dump_json() + '\n\n{"note": "duplicate emission"}'
    parsed = QuestionPlan.model_validate(_loads_json(payload))
    assert parsed.model_dump() == plan.model_dump()
