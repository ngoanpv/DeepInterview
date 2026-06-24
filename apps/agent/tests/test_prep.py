"""Offline tests for the WP-6 prep pipeline (LangGraph + MockLLM).

These exercise ``run_prep`` end-to-end with the deterministic default adapters
(MockLLM / MockSearch / MemoryRepository), so they require no API keys and no
network. The CV URL points at an unreachable host on purpose, to confirm
``fetch_cv`` tolerates an offline fetch and the pipeline still completes.
"""

from __future__ import annotations

import asyncio

from deepinterview_agent.core.deps import build_deps
from deepinterview_agent.prep import run_prep
from deepinterview_agent.shared_models import InterviewContext, LanguageMode, PrepRequest


def _request(primary: str = "en", mixed: bool = False) -> PrepRequest:
    return PrepRequest(
        cv_url="https://example.com/cv.pdf",
        jd_text="Senior Backend Engineer building distributed payment systems in Python.",
        company="ExampleCorp",
        language_mode=LanguageMode(primary=primary, mixed=mixed),
    )


def test_run_prep_produces_ready_interview_context() -> None:
    deps = build_deps()
    session_id = asyncio.run(run_prep(_request(), deps))

    assert session_id
    assert session_id.startswith("sess_")

    ctx = asyncio.run(deps.repo.load_context(session_id))
    assert ctx is not None
    assert isinstance(ctx, InterviewContext)
    assert ctx.session_id == session_id

    # Every sub-document is present and valid (model_validate ran on load).
    assert ctx.candidate is not None
    assert ctx.job is not None
    assert ctx.company is not None
    assert ctx.gap is not None
    assert ctx.plan is not None

    # The plan must carry at least one well-formed question.
    assert ctx.plan.questions, "expected a non-empty question plan"
    for q in ctx.plan.questions:
        assert 1 <= q.difficulty <= 5, f"difficulty {q.difficulty} out of 1..5"
        assert q.text.get("en"), "question text must include an 'en' entry"
        assert q.followups, "each question needs >= 1 seeded followup"
        assert q.target_competency, "each question needs a target_competency"
        assert q.rubric, "each question needs >= 1 rubric item"

    # Session status was flipped to ready (MemoryRepository inspection helper).
    assert deps.repo.get_status(session_id) == "ready"


def test_run_prep_pins_language_mode_for_non_english() -> None:
    deps = build_deps()
    session_id = asyncio.run(run_prep(_request(primary="vi", mixed=True), deps))

    ctx = asyncio.run(deps.repo.load_context(session_id))
    assert ctx is not None
    # run_prep pins the plan's language_mode to the request.
    assert ctx.plan.language_mode.primary == "vi"
    assert ctx.plan.language_mode.mixed is True


def test_run_prep_maps_search_results_into_company_citations() -> None:
    deps = build_deps()
    session_id = asyncio.run(run_prep(_request(), deps))

    ctx = asyncio.run(deps.repo.load_context(session_id))
    assert ctx is not None
    # MockSearch returns results, which the company_research node maps to citations.
    assert ctx.company.citations, "expected company citations from search results"
    for c in ctx.company.citations:
        assert c.title
        assert c.url


class _RecordingKnowledge:
    """Knowledge adapter spy: records ingest calls so a test can assert that prep
    closed the WP-8 loop with the right key + documents."""

    def __init__(self) -> None:
        self.ingests: list[tuple[str, list[str]]] = []

    async def search(self, user_id: str, query: str, lang: str):  # noqa: ANN201
        return ("", [])

    async def ingest(self, user_id: str, files: list[str]) -> str:
        self.ingests.append((user_id, list(files)))
        return f"trk-{user_id}-{len(files)}"


def test_run_prep_ingests_materials_keyed_by_session_id(monkeypatch) -> None:
    """Prep must ingest the CV/JD/company intel into the knowledge store keyed by
    session_id — the SAME key the Study Coach retrieves with — so the grounded
    coach loop is reachable (the WP-8 acceptance was structurally unmet before)."""
    deps = build_deps()
    recorder = _RecordingKnowledge()
    monkeypatch.setattr(deps, "knowledge", recorder)

    session_id = asyncio.run(run_prep(_request(), deps))

    assert recorder.ingests, "prep must ingest the prep materials"
    key, files = recorder.ingests[0]
    # Keyed by session_id (not user.id) — aligns ingest with the coach's query key.
    assert key == session_id
    blob = "\n\n".join(files)
    assert "CANDIDATE CV" in blob
    assert "JOB DESCRIPTION" in blob
    # The actual JD content is carried through, not just a header.
    assert "distributed payment systems" in blob


def test_run_prep_ingest_failure_does_not_break_prep(monkeypatch) -> None:
    """A knowledge-ingest failure must NEVER turn a successful prep into 'error':
    ingestion is strictly best-effort and self-contained."""
    deps = build_deps()

    class _BoomKnowledge(_RecordingKnowledge):
        async def ingest(self, user_id: str, files: list[str]) -> str:
            raise RuntimeError("kb sidecar down")

    monkeypatch.setattr(deps, "knowledge", _BoomKnowledge())
    session_id = asyncio.run(run_prep(_request(), deps))
    assert deps.repo.get_status(session_id) == "ready"
