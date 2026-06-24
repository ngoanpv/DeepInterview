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


async def _guarded(coro, *, label: str, timeout: float):
    """Await ``coro`` with a timeout; on ANY error return ``None`` (caller falls back)."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except Exception:  # noqa: BLE001 - kb endpoints must always return something usable
        log.exception("kb: stage %r failed; degrading", label)
        return None


@router.post("/api/kb/ingest", response_model=KbIngestResponse)
async def kb_ingest(req: KbIngestRequest) -> KbIngestResponse:
    # Ingest goes through the SAME knowledge adapter as /api/kb/query, so the
    # store key (user_id) and backend selection stay consistent across both
    # paths. With no LIGHTRAG_URL the adapter is MockKnowledge (deterministic
    # offline stub); when configured it forwards to the sidecar's /kb/ingest and
    # degrades to the stub on any failure rather than 5xx.
    deps = build_deps()
    track_id = await _guarded(
        deps.knowledge.ingest(req.user_id, req.files),
        label="ingest",
        timeout=_INGEST_TIMEOUT,
    )
    if track_id is None:
        track_id = f"trk-{req.user_id}-{len(req.files)}"
    return KbIngestResponse(track_id=track_id)


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
