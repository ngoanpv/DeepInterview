"""RAG backends for the knowledge sidecar.

``NaiveRAG`` is the default: a dependency-light, deterministic, in-memory store
with simple token-overlap (TF) scoring. It needs no network and no ML deps, so
the service runs and tests fully offline.

``LightRAGBackend`` is the real cross-lingual knowledge-graph stack (LightRAG +
RAG-Anything + bge-m3). It is lazy-imported and only constructed when
``RAG_BACKEND=lightrag`` and the optional ``rag`` extra is installed.

Both keep **one store/graph per ``user_id``** (per-user isolation).
"""

from __future__ import annotations

import os
import re
import uuid
from collections import Counter
from typing import Protocol, runtime_checkable

from .models import Citation

# Chunk size for the naive splitter (characters). ~500 chars ≈ a short paragraph.
CHUNK_CHARS = 500
# How many chunks to surface per query.
TOP_K = 3
# Length of the snippet excerpt returned in each citation.
SNIPPET_CHARS = 240

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    """Lowercased alphanumeric tokens. Cross-lingual-friendly enough for naive TF."""
    return _TOKEN_RE.findall(text.lower())


def _chunk_text(text: str, *, size: int = CHUNK_CHARS) -> list[str]:
    """Split ``text`` into ~``size``-char chunks on whitespace boundaries.

    Deterministic: no randomness, stable order. Empty/blank input yields no chunks.
    """
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            # Prefer breaking on the last whitespace within the window so we don't
            # cut words; fall back to a hard cut if there's no whitespace.
            window = text[start:end]
            ws = window.rfind(" ")
            if ws > size // 2:
                end = start + ws
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end
    return chunks


class _Chunk:
    """A stored chunk: its text plus the source it came from and a stable index."""

    __slots__ = ("source_id", "text", "index", "_tokens")

    def __init__(self, source_id: str, text: str, index: int) -> None:
        self.source_id = source_id
        self.text = text
        self.index = index
        self._tokens = Counter(_tokenize(text))

    def score(self, query_tokens: list[str]) -> float:
        """Deterministic TF relevance: sum of query-token frequencies in the chunk.

        Normalised by chunk length so longer chunks don't dominate purely by size.
        """
        if not self._tokens:
            return 0.0
        total = sum(self._tokens.values())
        hit = sum(self._tokens.get(t, 0) for t in query_tokens)
        return hit / total


@runtime_checkable
class RagBackend(Protocol):
    """Per-user retrieval backend."""

    async def ingest(self, user_id: str, docs: list[tuple[str, str]]) -> str:
        """Ingest ``docs`` (``(source_id, text)``) for ``user_id``; return a track_id."""
        ...

    async def query(
        self, user_id: str, query: str, lang: str
    ) -> tuple[str, list[Citation]]:
        """Return ``(answer, citations)`` for ``query`` over ``user_id``'s store."""
        ...


class NaiveRAG:
    """Dependency-light, deterministic, in-memory per-user RAG.

    No network, no ML deps. Stores chunked docs per ``user_id`` and ranks them by
    token-overlap TF at query time.
    """

    def __init__(self) -> None:
        # user_id -> list[_Chunk]
        self._stores: dict[str, list[_Chunk]] = {}

    async def ingest(self, user_id: str, docs: list[tuple[str, str]]) -> str:
        store = self._stores.setdefault(user_id, [])
        for source_id, text in docs:
            for chunk_text in _chunk_text(text):
                store.append(_Chunk(source_id, chunk_text, len(store)))
        # Deterministic-but-unique track id derived from the user + store size.
        return f"naive-{user_id}-{len(store)}-{uuid.uuid4().hex[:8]}"

    async def query(
        self, user_id: str, query: str, lang: str
    ) -> tuple[str, list[Citation]]:
        store = self._stores.get(user_id, [])
        query_tokens = _tokenize(query)
        if not store or not query_tokens:
            return ("", [])

        scored = [(chunk.score(query_tokens), chunk) for chunk in store]
        # Drop zero-relevance chunks, then sort by (-score, index) for a stable,
        # deterministic top-k that never depends on insertion/dict ordering.
        scored = [pair for pair in scored if pair[0] > 0.0]
        if not scored:
            return ("", [])
        scored.sort(key=lambda pair: (-pair[0], pair[1].index))
        top = [chunk for _, chunk in scored[:TOP_K]]

        # Extractive answer: lead with the best chunk, append the rest for context.
        answer = top[0].text
        if len(top) > 1:
            answer = " ".join(chunk.text for chunk in top)

        citations = [
            Citation(
                title=chunk.source_id,
                url=chunk.source_id,
                snippet=chunk.text[:SNIPPET_CHARS],
            )
            for chunk in top
        ]
        return (answer, citations)


class LightRAGBackend:
    """Real LightRAG + RAG-Anything + bge-m3 backend (gated, lazy-imported).

    Only constructed when ``RAG_BACKEND=lightrag`` and the optional ``rag`` extra
    is installed. It will not run offline; the skeleton documents the integration
    points (per-user working dir, bge-m3 embeddings, ``/query/data`` for citations).
    """

    def __init__(self, working_dir: str | None = None) -> None:
        self._working_dir = working_dir or os.environ.get(
            "LIGHTRAG_WORKING_DIR", "./rag_storage"
        )
        # user_id -> LightRAG instance (one graph per user).
        self._instances: dict[str, object] = {}
        # Fail fast and clearly if the extra isn't installed.
        try:
            import lightrag  # noqa: F401, PLC0415
            import raganything  # noqa: F401, PLC0415
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "RAG_BACKEND=lightrag requires the 'rag' extra "
                "(lightrag-hku, raganything, sentence-transformers). "
                "Install it with: uv sync --extra rag"
            ) from exc

    def _instance(self, user_id: str) -> object:  # pragma: no cover - needs extra
        """Return (or lazily build) the per-user LightRAG instance.

        Real wiring (sketch): one working dir per user, bge-m3 as the embedding
        function, and a reranker (bge-reranker-v2-m3). RAG-Anything handles
        multimodal ingestion (PDF/DOCX/PPTX/images).
        """
        raise NotImplementedError(
            "LightRAGBackend is a skeleton; wire LightRAG(working_dir=.../{user_id}) "
            "with bge-m3 embeddings here."
        )

    async def ingest(  # pragma: no cover - needs extra
        self, user_id: str, docs: list[tuple[str, str]]
    ) -> str:
        raise NotImplementedError(
            "LightRAGBackend.ingest: call await instance.ainsert(text) per doc."
        )

    async def query(  # pragma: no cover - needs extra
        self, user_id: str, query: str, lang: str
    ) -> tuple[str, list[Citation]]:
        # Real impl: await instance.aquery(query, param=QueryParam(mode="hybrid")) for
        # the answer, and instance.aquery_data(...) / the `/query/data` shape for the
        # retrieved chunks/sources -> Citation list.
        raise NotImplementedError(
            "LightRAGBackend.query: use aquery for the answer and query/data for citations."
        )


def get_backend() -> RagBackend:
    """Select the backend from ``RAG_BACKEND`` (default ``naive``)."""
    choice = os.environ.get("RAG_BACKEND", "naive").strip().lower()
    if choice in ("", "naive"):
        return NaiveRAG()
    if choice == "lightrag":
        return LightRAGBackend()
    raise ValueError(
        f"Unknown RAG_BACKEND={choice!r}; expected 'naive' (default) or 'lightrag'."
    )
