"""Offline tests for server-side CV/résumé document extraction.

No network, no real Gemini: the http-fetch path isn't exercised (the prep suite
covers the unreachable-URL fallback), and the Gemini fallback is monkeypatched.
markitdown IS exercised for real on text/markdown data URLs — proving an uploaded
document is decoded and converted, which is the whole point of the fix.
"""

from __future__ import annotations

import asyncio
import base64

from deepinterview_agent.core.config import Settings
from deepinterview_agent.core.deps import build_deps
from deepinterview_agent.prep import cv_extract
from deepinterview_agent.prep.cv_extract import extract_cv_text
from deepinterview_agent.prep.nodes import fetch_cv
from deepinterview_agent.shared_models import LanguageMode, PrepRequest

_REAL_CV = (
    "Jane Doe — Senior Backend Engineer. 8 years of Python, Kafka, and "
    "distributed payment systems. Led three teams and owned service reliability."
)


def _data_url(text: str, mime: str = "text/plain") -> str:
    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return f"data:{mime};base64,{b64}"


def test_plain_text_passthrough_unchanged() -> None:
    """The paste path: arbitrary text is returned verbatim, never parsed."""
    deps = build_deps()
    text, warnings = asyncio.run(extract_cv_text(_REAL_CV, deps))
    assert text == _REAL_CV
    assert warnings == []


def test_data_url_text_is_decoded_and_converted() -> None:
    """A base64 data: URL of a CV paragraph decodes + markitdown-converts to it."""
    deps = build_deps()
    url = _data_url(_REAL_CV, mime="text/plain")
    text, warnings = asyncio.run(extract_cv_text(url, deps))
    assert "Jane Doe" in text
    assert "distributed payment systems" in text
    assert warnings == []


def test_markitdown_handles_markdown_data_url() -> None:
    """markitdown converts a real markdown document data URL to plain text."""
    deps = build_deps()
    md = f"# Résumé\n\n## Summary\n\n{_REAL_CV}\n\n- Python\n- Kafka\n"
    url = _data_url(md, mime="text/markdown")
    text, warnings = asyncio.run(extract_cv_text(url, deps))
    assert "Jane Doe" in text
    assert warnings == []


def test_gemini_fallback_used_when_markitdown_empty(monkeypatch) -> None:
    """When markitdown yields nothing, the Gemini fallback is invoked and used."""
    # Gemini guard requires provider=gemini AND a key present (deps.llm is the
    # mock — irrelevant, the fallback uses its own genai client we monkeypatch).
    deps = build_deps(Settings(llm_provider="gemini", gemini_api_key="test-key"))

    calls = {"markitdown": 0, "gemini": 0}

    def _empty_markitdown(data: bytes, mime: str) -> str:
        calls["markitdown"] += 1
        return ""

    async def _fake_gemini(data: bytes, mime: str, d) -> str:
        calls["gemini"] += 1
        return _REAL_CV

    monkeypatch.setattr(cv_extract, "_markitdown_extract", _empty_markitdown)
    monkeypatch.setattr(cv_extract, "_gemini_extract", _fake_gemini)

    url = _data_url("ignored — markitdown is stubbed to empty", mime="application/pdf")
    text, warnings = asyncio.run(extract_cv_text(url, deps))

    assert text == _REAL_CV
    assert warnings == []
    assert calls["markitdown"] == 1
    assert calls["gemini"] == 1


def test_gemini_fallback_not_called_when_markitdown_succeeds(monkeypatch) -> None:
    """A successful markitdown extraction short-circuits — Gemini is never called."""
    deps = build_deps(Settings(llm_provider="gemini", gemini_api_key="test-key"))

    calls = {"gemini": 0}

    async def _fake_gemini(data: bytes, mime: str, d) -> str:
        calls["gemini"] += 1
        return "SHOULD NOT BE USED"

    monkeypatch.setattr(cv_extract, "_gemini_extract", _fake_gemini)

    url = _data_url(_REAL_CV, mime="text/plain")
    text, warnings = asyncio.run(extract_cv_text(url, deps))

    assert "Jane Doe" in text
    assert calls["gemini"] == 0
    assert warnings == []


def test_unreadable_document_warns_and_returns_empty(monkeypatch) -> None:
    """Both extractors fail (no Gemini configured) -> empty text + a warning."""
    deps = build_deps()  # provider=mock, no gemini key -> fallback guard is False

    monkeypatch.setattr(cv_extract, "_markitdown_extract", lambda data, mime: "")

    url = _data_url("x", mime="application/pdf")
    text, warnings = asyncio.run(extract_cv_text(url, deps))

    assert text == ""
    assert len(warnings) == 1
    assert "Couldn't read" in warnings[0]


def _prep_request(cv_url: str) -> PrepRequest:
    return PrepRequest(
        cv_url=cv_url,
        jd_text="We are hiring a backend engineer to build payment systems.",
        company="Acme",
        language_mode=LanguageMode(primary="en", mixed=False),
    )


def test_fetch_cv_node_is_idempotent_even_when_text_empty(monkeypatch) -> None:
    """An already-resolved (even empty) cv_text must not be re-parsed.

    Regression guard: the no-op checks key *presence*, not truthiness, so an
    unreadable document (cv_text == "") doesn't re-run extraction — which would
    re-warn and re-bill Gemini.
    """
    called = {"extract": 0}

    async def _boom(cv_url: str, d):  # pragma: no cover - must never run
        called["extract"] += 1
        return "should not be called", []

    monkeypatch.setattr("deepinterview_agent.prep.nodes.extract_cv_text", _boom)

    deps = build_deps()
    state = {"req": _prep_request("data:text/plain;base64,xxxx"), "cv_text": ""}
    result = asyncio.run(fetch_cv(state, deps))

    assert result == {}
    assert called["extract"] == 0
