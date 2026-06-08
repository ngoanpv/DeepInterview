"""Round-trip + invariant tests for the Pydantic mirror of packages/shared."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from deepinterview_agent.shared_models import InterviewContext, PlannedQuestion

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "packages/shared/fixtures/interview-context.sample.json"
)


def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_interview_context_round_trips() -> None:
    data = _load_fixture()
    ctx = InterviewContext.model_validate(data)
    dumped = ctx.model_dump()
    # Re-validating the dumped dict must yield an equal model.
    reparsed = InterviewContext.model_validate(dumped)
    assert reparsed == ctx
    assert reparsed.model_dump() == dumped


def test_localized_text_requires_en() -> None:
    base = _load_fixture()["plan"]["questions"][0]
    bad = {**base, "text": {"vi": "xin chào"}}
    with pytest.raises(ValidationError):
        PlannedQuestion.model_validate(bad)
