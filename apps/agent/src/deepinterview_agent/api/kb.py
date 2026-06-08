"""``/api/kb`` — knowledge-base ingest + grounded query (Phase 2 RAG).

``POST /api/kb/ingest`` accepts files for a user's knowledge store. When a
``lightrag_url`` is configured it forwards the ingest to the LightRAG sidecar
(``httpx`` POST ``${lightrag_url}/kb/ingest``); with no URL it returns a
deterministic stub :class:`KbIngestResponse` so the endpoint works fully offline.

``POST /api/kb/query`` answers a grounded question over the user's store via
``deps.knowledge.search(...)`` — the same retrieval path the Study Coach uses —
and returns a :class:`KbQueryResponse`.

Every network/retrieval call is guarded with a timeout + fallback (mirroring
``coach/__init__.py``) so the endpoint always returns a valid response.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter

from ..core.deps import build_deps
from ..core.logging import get_logger
from ..shared_models import (
    KbIngestRequest,
    KbIngestResponse,
    KbQueryRequest,
    KbQueryResponse,
)

log = get_logger(__name__)

router = APIRouter()

# Timeout when forwarding an ingest to the knowledge sidecar (seconds). Mirrors
# adapters/knowledge.py's ``_QUERY_TIMEOUT`` — ingest is heavier, so allow longer.
_INGEST_TIMEOUT = 60.0
# Timeout for a grounded query (seconds).
_QUERY_TIMEOUT = 20.0


def _stub_track_id(req: KbIngestRequest) -> str:
    """Deterministic offline track id: stable for a given user + file set.

    No ``uuid4``/``hash()`` (both non-deterministic across runs) — a plain f-string
    keeps the stub reproducible so callers can assert on it.
    """
    return f"trk-{req.user_id}-{len(req.files)}"


async def _guarded(coro, *, label: str, timeout: float):
    """Await ``coro`` with a timeout; on ANY error return ``None`` (caller falls back)."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except Exception:  # noqa: BLE001 - kb endpoints must always return something usable
        log.exception("kb: stage %r failed; degrading", label)
        return None


async def _forward_ingest(base_url: str, req: KbIngestRequest) -> KbIngestResponse | None:
    """POST the ingest to the LightRAG sidecar's ``/kb/ingest``; ``None`` on failure."""
    import httpx  # noqa: PLC0415 - httpx is a core agent dep; lazy keeps import cheap

    payload = {"user_id": req.user_id, "files": req.files}
    async with httpx.AsyncClient(timeout=_INGEST_TIMEOUT) as client:
        resp = await client.post(f"{base_url.rstrip('/')}/kb/ingest", json=payload)
        resp.raise_for_status()
        data = resp.json()
    return KbIngestResponse(track_id=data.get("track_id", _stub_track_id(req)))


@router.post("/api/kb/ingest", response_model=KbIngestResponse)
async def kb_ingest(req: KbIngestRequest) -> KbIngestResponse:
    deps = build_deps()
    base_url = deps.settings.lightrag_url
    if base_url:
        forwarded = await _guarded(
            _forward_ingest(base_url, req), label="ingest", timeout=_INGEST_TIMEOUT
        )
        if forwarded is not None:
            return forwarded
        # Sidecar configured but unreachable: degrade to the offline stub rather
        # than 5xx, mirroring the coach's degrade-don't-raise policy.
    return KbIngestResponse(track_id=_stub_track_id(req))


@router.post("/api/kb/query", response_model=KbQueryResponse)
async def kb_query(req: KbQueryRequest) -> KbQueryResponse:
    deps = build_deps()
    grounded = await _guarded(
        deps.knowledge.search(req.user_id, req.query, req.lang),
        label="knowledge",
        timeout=_QUERY_TIMEOUT,
    )
    if grounded is None:
        return KbQueryResponse(
            answer="I couldn't reach the knowledge base just now — try again in a moment.",
            citations=[],
        )
    answer, citations = grounded
    return KbQueryResponse(answer=answer, citations=list(citations))
