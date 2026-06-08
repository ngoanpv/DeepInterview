"""Offline tests for the NaiveRAG backend + app wiring.

These exercise the backend directly (``asyncio.run``) rather than via Starlette's
TestClient, because TestClient pulls in httpx — which is intentionally NOT a
dependency of this service. The naive backend is fully deterministic and needs no
network or ML deps.
"""

from __future__ import annotations

import asyncio

from lightrag_service.app import create_app
from lightrag_service.backend import NaiveRAG, get_backend
from lightrag_service.models import Citation


def _run(coro):
    return asyncio.run(coro)


def test_query_returns_relevant_chunk_and_citation() -> None:
    backend = NaiveRAG()
    _run(
        backend.ingest(
            "user-a",
            [
                ("cv.txt", "Jane built a payments platform handling 2M transactions."),
                ("notes.txt", "The candidate enjoys hiking and photography on weekends."),
            ],
        )
    )
    answer, citations = _run(backend.query("user-a", "payments platform", "en"))

    assert "payments" in answer.lower()
    assert len(citations) >= 1
    assert all(isinstance(c, Citation) for c in citations)
    # The top citation comes from the relevant source and quotes the matched text.
    assert citations[0].title == "cv.txt"
    assert citations[0].url == "cv.txt"
    assert "payments" in (citations[0].snippet or "").lower()


def test_per_user_isolation() -> None:
    backend = NaiveRAG()
    _run(backend.ingest("alice", [("a.txt", "Alice specialises in distributed systems.")]))
    _run(backend.ingest("bob", [("b.txt", "Bob specialises in mobile development.")]))

    # Bob's query must not surface Alice's document.
    answer, citations = _run(backend.query("bob", "distributed systems", "en"))
    assert "alice" not in answer.lower()
    assert all(c.title != "a.txt" for c in citations)

    # And the reverse: Alice gets her own content.
    a_answer, a_citations = _run(backend.query("alice", "distributed systems", "en"))
    assert "distributed" in a_answer.lower()
    assert any(c.title == "a.txt" for c in a_citations)


def test_query_is_deterministic() -> None:
    def build_and_query() -> tuple[str, list[dict]]:
        backend = NaiveRAG()
        _run(
            backend.ingest(
                "u",
                [
                    ("doc1", "Kubernetes orchestrates containers across a cluster."),
                    ("doc2", "Docker packages an application into a container image."),
                    ("doc3", "Containers share the host kernel and start fast."),
                ],
            )
        )
        ans, cites = _run(backend.query("u", "container container kernel", "en"))
        return ans, [c.model_dump() for c in cites]

    a = build_and_query()
    b = build_and_query()
    assert a == b


def test_empty_or_unmatched_query_returns_empty() -> None:
    backend = NaiveRAG()
    _run(backend.ingest("u", [("d.txt", "Some unrelated content about cooking.")]))
    answer, citations = _run(backend.query("u", "quantum chromodynamics", "en"))
    assert answer == ""
    assert citations == []

    # Unknown user -> empty, no leak.
    answer2, citations2 = _run(backend.query("nobody", "cooking", "en"))
    assert answer2 == ""
    assert citations2 == []


def test_get_backend_defaults_to_naive(monkeypatch) -> None:
    monkeypatch.delenv("RAG_BACKEND", raising=False)
    assert isinstance(get_backend(), NaiveRAG)
    monkeypatch.setenv("RAG_BACKEND", "naive")
    assert isinstance(get_backend(), NaiveRAG)


def test_app_exposes_kb_routes() -> None:
    app = create_app(backend=NaiveRAG())
    paths = {route.path for route in app.routes}
    assert "/health" in paths
    assert "/kb/ingest" in paths
    assert "/kb/query" in paths
