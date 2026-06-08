"""Offline tests for the FastAPI app (health + prep flow)."""

from fastapi.testclient import TestClient

from deepinterview_agent.app import create_app
from deepinterview_agent.core.persistence import repository as repo_mod


def _client() -> TestClient:
    return TestClient(create_app())


def test_health_ok() -> None:
    resp = _client().get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_prep_endpoint_creates_ready_session() -> None:
    client = _client()
    body = {
        "cv_url": "https://example.com/cv.pdf",
        "jd_text": "Senior backend engineer building distributed payment systems in Python.",
        "company": "Acme Payments",
        "language_mode": {"primary": "en", "mixed": False},
    }
    resp = client.post("/api/prep", json=body)
    assert resp.status_code == 200

    data = resp.json()
    session_id = data["session_id"]
    assert session_id.startswith("sess_")

    # POST returns immediately, but Starlette's TestClient runs the BackgroundTask
    # to completion before returning, so the session is already 'ready' via GET.
    view = client.get(f"/api/session/{session_id}")
    assert view.status_code == 200
    payload = view.json()
    assert payload["session_id"] == session_id
    assert payload["status"] == "ready"
    # All five prep agents reported completion (order is non-deterministic).
    assert set(payload["progress"]) == {
        "cv_analysis",
        "jd_analysis",
        "company_research",
        "gap_matching",
        "question_planner",
    }
    assert payload["context"] is not None
    assert payload["context"]["session_id"] == session_id

    # The route uses the module-singleton MemoryRepository (no Supabase configured),
    # so the session it wrote is inspectable here too.
    assert repo_mod._MEMORY_REPO.get_status(session_id) == "ready"


def test_session_endpoint_404_for_unknown_id() -> None:
    resp = _client().get("/api/session/sess_does_not_exist")
    assert resp.status_code == 404


def test_prep_endpoint_rejects_garbage_input() -> None:
    client = _client()
    body = {
        # Both CV and JD are meaningless -> the session is rejected.
        "cv_url": "asdasdasdasdasdasd",
        "jd_text": "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!",
        "company": "Acme Payments",
        "language_mode": {"primary": "en", "mixed": False},
    }
    resp = client.post("/api/prep", json=body)
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    view = client.get(f"/api/session/{session_id}")
    assert view.status_code == 200
    payload = view.json()
    assert payload["status"] == "rejected"
    assert payload["prep_warnings"], "rejection must surface warnings to the UI"
    assert payload["context"] is None
