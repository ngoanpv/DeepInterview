"""Offline tests for the knowledge adapter (WP-8 agent client).

These import ONLY ``core.adapters.knowledge`` — never ``live.kb_tool`` (which needs
the livekit extra) — so the suite stays green with livekit absent.
"""

from __future__ import annotations

import asyncio

from deepinterview_agent.core.adapters.knowledge import (
    HttpKnowledge,
    KnowledgeClient,
    MockKnowledge,
    get_knowledge,
)
from deepinterview_agent.core.config import Settings
from deepinterview_agent.shared_models import Citation


def _run(coro):
    return asyncio.run(coro)


def test_mock_knowledge_returns_answer_and_shared_citations() -> None:
    answer, citations = _run(MockKnowledge().search("u1", "system design", "en"))
    assert isinstance(answer, str) and answer
    assert "system design" in answer
    assert len(citations) == 2
    assert all(isinstance(c, Citation) for c in citations)


def test_mock_knowledge_is_deterministic() -> None:
    a = _run(MockKnowledge().search("u1", "graphs", "en"))
    b = _run(MockKnowledge().search("u1", "graphs", "en"))
    assert a[0] == b[0]
    assert [c.model_dump() for c in a[1]] == [c.model_dump() for c in b[1]]


def test_mock_knowledge_satisfies_protocol() -> None:
    assert isinstance(MockKnowledge(), KnowledgeClient)
    assert isinstance(HttpKnowledge("http://localhost:9621"), KnowledgeClient)


def test_get_knowledge_returns_mock_without_lightrag_url(monkeypatch) -> None:
    monkeypatch.delenv("LIGHTRAG_URL", raising=False)
    client = get_knowledge(Settings())
    assert isinstance(client, MockKnowledge)
    # And it yields a (answer, citations) tuple of shared Citation instances.
    answer, citations = _run(client.search("u1", "behavioral", "en"))
    assert isinstance(answer, str)
    assert all(isinstance(c, Citation) for c in citations)


def test_get_knowledge_returns_http_with_lightrag_url(monkeypatch) -> None:
    monkeypatch.setenv("LIGHTRAG_URL", "http://lightrag:9621")
    client = get_knowledge(Settings())
    assert isinstance(client, HttpKnowledge)
