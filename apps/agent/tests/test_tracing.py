"""Tests for local-first tracing (WP-12): spans, LLM wrapper, pipeline hooks.

Tracing is OFF by default in this suite (``tests/conftest.py`` sets
``TRACE_ENABLED=0``). Each test opts back in with
``tracing.init_tracing(enabled=True, trace_dir=tmp_path)`` and resets
afterwards, so no test writes into the repo checkout.
"""

from __future__ import annotations

import asyncio
import contextvars
import json

import pytest
from fastapi.testclient import TestClient

from deepinterview_agent.app import create_app
from deepinterview_agent.core import tracing
from deepinterview_agent.core.adapters.mock import MockLLM
from deepinterview_agent.core.deps import build_deps
from deepinterview_agent.shared_models import LanguageMode, PrepRequest


@pytest.fixture
def tracedir(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACE_ENABLED", "1")
    tracing.init_tracing(enabled=True, trace_dir=tmp_path, include_prompts=False)
    yield tmp_path
    tracing.reset_tracing()
    monkeypatch.setenv("TRACE_ENABLED", "0")


def _events(tracedir, trace_id):
    path = tracedir / f"{trace_id}.jsonl"
    assert path.exists(), f"expected trace file for {trace_id}"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _request() -> PrepRequest:
    return PrepRequest(
        cv_url="https://example.com/cv.pdf",
        jd_text="Senior Backend Engineer building distributed payment systems in Python.",
        company="ExampleCorp",
        language_mode=LanguageMode(primary="en", mixed=False),
    )


def test_start_trace_and_nested_spans(tracedir) -> None:
    with tracing.start_trace("demo", session_id="sess_x", metadata={"k": "v"}) as tid:
        assert tid.startswith("tr_")
        with tracing.start_span("outer", step=1):
            tracing.add_event("note", {"a": 1})
            with tracing.start_span("inner"):
                pass
    events = _events(tracedir, tid)
    types = [e["type"] for e in events]
    assert types[0] == "trace_start"
    assert types[-1] == "trace_end"
    assert events[0]["session_id"] == "sess_x"
    assert events[-1]["status"] == "ok"
    span_starts = [e for e in events if e["type"] == "span_start"]
    assert [s["name"] for s in span_starts] == ["outer", "inner"]
    # Nesting: inner's parent is outer.
    assert span_starts[1]["parent_id"] == span_starts[0]["span_id"]
    assert any(e["type"] == "event" and e["name"] == "note" for e in events)


def test_trace_can_close_from_a_different_context(tracedir) -> None:
    """LiveKit opens a live trace in entrypoint and closes it in shutdown.

    Those callbacks run in different asyncio Contexts, where resetting the
    entrypoint's ContextVar token raises ValueError unless tracing treats the
    close as detached. The trace must still end cleanly because persistence and
    scoring run immediately afterwards in the same shutdown callback.
    """
    trace = tracing.start_trace("live", session_id="sess_cross_context")
    tid = trace.__enter__()

    contextvars.Context().run(trace.__exit__, None, None, None)

    events = _events(tracedir, tid)
    assert [e["type"] for e in events].count("trace_end") == 1
    assert events[-1]["status"] == "ok"


def test_span_error_is_recorded_not_raised_past_trace(tracedir) -> None:
    with (
        tracing.start_trace("boom") as tid,
        pytest.raises(ValueError, match="nope"),
        tracing.start_span("risky"),
    ):
        raise ValueError("nope")
    events = _events(tracedir, tid)
    span_end = next(e for e in events if e["type"] == "span_end")
    assert span_end["status"] == "error"
    assert "ValueError" in span_end["error"]
    assert next(e for e in events if e["type"] == "trace_end")["status"] == "ok"


def test_traced_decorator_names_span(tracedir) -> None:
    @tracing.traced("custom.name")
    async def work() -> str:
        return "done"

    assert asyncio.run(work()) == "done"
    files = list(tracedir.glob("tr_*.jsonl"))
    assert len(files) == 1  # auto-trace: decorator outside a trace still records
    events = [json.loads(line) for line in files[0].read_text().splitlines()]
    assert events[0]["type"] == "trace_start"
    assert events[0]["name"] == "auto"
    assert any(e["type"] == "span_start" and e["name"] == "custom.name" for e in events)


def test_traced_llm_records_calls(tracedir) -> None:
    from deepinterview_agent.shared_models import JobSpec

    llm = tracing.TracedLLM(MockLLM(), provider="mock")
    with tracing.start_trace("llm-demo") as tid:
        asyncio.run(llm.complete_text(system="sys", user="hello"))
        asyncio.run(llm.complete_json(system="sys", user="{}", schema=JobSpec))
    events = _events(tracedir, tid)
    calls = [e for e in events if e["type"] == "llm_call"]
    assert len(calls) == 2
    assert calls[0]["method"] == "complete_text"
    assert calls[1]["schema"] == "JobSpec"
    assert all(c["ok"] for c in calls)
    # No prompt text by default (lengths only).
    assert "prompt_preview" not in calls[0]


def test_disabled_tracing_writes_nothing(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TRACE_ENABLED", "0")
    tracing.reset_tracing()
    with tracing.start_trace("nope") as tid:
        assert tid == "tr_disabled"
        with tracing.start_span("x") as sid:
            assert sid == "sp_disabled"
            tracing.add_event("y")
    assert list(tmp_path.glob("*.jsonl")) == []
    tracing.reset_tracing()


def test_prep_run_emits_trace(tracedir) -> None:
    from deepinterview_agent.core.config import Settings

    settings = Settings(
        llm_provider="mock",
        search_provider="mock",
        trace_enabled=True,
        trace_dir=str(tracedir),
    )
    deps = build_deps(settings)
    from deepinterview_agent.prep import run_prep

    session_id = asyncio.run(run_prep(_request(), deps))
    files = list(tracedir.glob("tr_*.jsonl"))
    assert len(files) == 1
    events = [json.loads(line) for line in files[0].read_text().splitlines()]
    assert events[0]["name"] == "prep"
    assert events[0]["session_id"] == session_id
    span_names = {e["name"] for e in events if e["type"] == "span_start"}
    assert {"prep.cv_analysis", "prep.question_planner", "llm.complete_json"} <= span_names
    assert any(e["type"] == "event" and e["name"] == "prep.ready" for e in events)


def test_score_run_emits_trace(tracedir) -> None:
    from deepinterview_agent.core.config import Settings
    from deepinterview_agent.post import run_score
    from deepinterview_agent.prep import run_prep
    from deepinterview_agent.shared_models import ScoreRequest

    settings = Settings(llm_provider="mock", search_provider="mock")
    deps = build_deps(settings)
    session_id = asyncio.run(run_prep(_request(), deps))
    # Give the interview an answer so scoring has something to score.
    ctx = asyncio.run(deps.repo.load_context(session_id))
    assert ctx is not None
    from deepinterview_agent.shared_models import AnswerRecord

    ctx.answers.append(
        AnswerRecord(
            question_id=ctx.plan.questions[0].id,
            transcript="We migrated the checkout service to an event-driven design.",
            started_at="",
            ended_at="",
        )
    )
    asyncio.run(deps.repo.save_context(session_id, ctx))

    tracing.reset_tracing()
    tracing.init_tracing(enabled=True, trace_dir=tracedir)
    card = asyncio.run(run_score(ScoreRequest(session_id=session_id), deps))
    assert card.overall_score >= 0

    files = list(tracedir.glob("tr_*.jsonl"))
    score_traces = [
        f for f in files if json.loads(f.read_text().splitlines()[0])["name"] == "score"
    ]
    assert score_traces, "expected a score trace"
    events = [json.loads(line) for line in score_traces[0].read_text().splitlines()]
    span_names = {e["name"] for e in events if e["type"] == "span_start"}
    assert {"post.evaluate", "post.coach", "post.report"} <= span_names


def test_traces_api_lists_and_shows(tracedir, monkeypatch) -> None:
    with tracing.start_trace("api-demo", session_id="sess_api") as tid, tracing.start_span("work"):
        pass
    monkeypatch.setenv("TRACE_DIR", str(tracedir))
    from deepinterview_agent.core.config import get_settings

    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        resp = client.get("/api/traces")
        assert resp.status_code == 200
        traces = resp.json()["traces"]
        assert any(t["trace_id"] == tid for t in traces)

        detail = client.get(f"/api/traces/{tid}")
        assert detail.status_code == 200
        assert detail.json()["trace_id"] == tid
        assert detail.json()["spans"]

        assert client.get("/api/traces/tr_nope").status_code == 404
    finally:
        get_settings.cache_clear()


def test_list_traces_filters_by_session(tracedir) -> None:
    with tracing.start_trace("a", session_id="sess_1"):
        pass
    with tracing.start_trace("b", session_id="sess_2"):
        pass
    all_traces = tracing.list_traces(directory=tracedir)
    assert len(all_traces) == 2
    only_one = tracing.list_traces(directory=tracedir, session_id="sess_1")
    assert [t["session_id"] for t in only_one] == ["sess_1"]
