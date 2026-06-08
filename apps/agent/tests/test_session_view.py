"""Offline tests for prep progress + the GET /api/session read model.

Exercises ``run_prep`` (inline) end-to-end with the deterministic adapters and
asserts the progress steps, the assembled SessionView, and the rejection path
for wholly meaningless input — all without network or API keys.
"""

from __future__ import annotations

import asyncio

from deepinterview_agent.api.views import PROGRESS_STEPS, SessionView
from deepinterview_agent.core.deps import build_deps
from deepinterview_agent.prep import run_prep
from deepinterview_agent.shared_models import LanguageMode, PrepRequest

_ALL_STEPS = set(PROGRESS_STEPS)


def _good_request() -> PrepRequest:
    return PrepRequest(
        cv_url="https://example.com/cv.pdf",
        jd_text="Senior Backend Engineer building distributed payment systems in Python.",
        company="ExampleCorp",
        language_mode=LanguageMode(primary="en", mixed=False),
    )


def _garbage_request() -> PrepRequest:
    return PrepRequest(
        cv_url="asdasdasdasdasdasdasd",
        jd_text="!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!",
        company="ExampleCorp",
        language_mode=LanguageMode(primary="en", mixed=False),
    )


def test_run_prep_records_all_five_progress_steps() -> None:
    deps = build_deps()
    session_id = asyncio.run(run_prep(_good_request(), deps))

    view = asyncio.run(deps.repo.get_session_view(session_id))
    assert isinstance(view, SessionView)
    assert view.status == "ready"
    # All five agents reported completion; order is non-deterministic (fan-out).
    assert set(view.progress) == _ALL_STEPS
    assert len(view.progress) == 5, "no duplicate progress entries"


def test_get_session_view_carries_context_when_ready() -> None:
    deps = build_deps()
    session_id = asyncio.run(run_prep(_good_request(), deps))

    view = asyncio.run(deps.repo.get_session_view(session_id))
    assert view is not None
    assert view.context is not None
    assert view.context.session_id == session_id
    assert view.context.plan.questions, "ready context must carry a plan"
    assert set(view.progress) == _ALL_STEPS


def test_get_session_view_unknown_returns_none() -> None:
    deps = build_deps()
    view = asyncio.run(deps.repo.get_session_view("sess_nope"))
    assert view is None


def test_run_prep_rejects_garbage_cv_and_jd() -> None:
    deps = build_deps()
    # Must not crash even though both core inputs are meaningless.
    session_id = asyncio.run(run_prep(_garbage_request(), deps))

    view = asyncio.run(deps.repo.get_session_view(session_id))
    assert view is not None
    assert view.status == "rejected"
    assert view.prep_warnings, "rejection must surface human-readable warnings"
    assert view.context is None
    # No graph ran -> no progress recorded.
    assert view.progress == []


def test_run_prep_junk_company_warns_but_completes() -> None:
    deps = build_deps()
    req = PrepRequest(
        cv_url="Jane Doe, backend engineer, 8 years Python microservices at fintech scale.",
        jd_text="Senior Backend Engineer building distributed payment systems in Python.",
        company="$",
        language_mode=LanguageMode(primary="en", mixed=False),
    )
    session_id = asyncio.run(run_prep(req, deps))

    view = asyncio.run(deps.repo.get_session_view(session_id))
    assert view is not None
    assert view.status == "ready"
    assert any("company name" in w for w in view.prep_warnings)
    # company_research still ran (short-circuited) and reported progress.
    assert set(view.progress) == _ALL_STEPS
    # Empty-but-valid company intel (no fabricated knowledge).
    assert view.context is not None
    assert view.context.company.summary == ""
