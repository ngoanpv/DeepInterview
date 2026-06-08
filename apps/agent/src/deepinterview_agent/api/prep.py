"""``POST /api/prep`` — kick off the prep pipeline for a CV + JD + company.

Returns immediately with a ``session_id`` (status ``prep``); the heavy pipeline
runs in a FastAPI ``BackgroundTask`` and the client polls ``GET /api/session/{id}``
for progress + the final context. (Under Starlette's ``TestClient`` the background
task runs to completion before the response is returned.)
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from ..core.deps import build_deps
from ..prep import run_prep_for_session
from ..shared_models import PrepRequest, PrepResponse

router = APIRouter()


@router.post("/api/prep", response_model=PrepResponse)
async def prep(req: PrepRequest, background_tasks: BackgroundTasks) -> PrepResponse:
    deps = build_deps()
    session_id = await deps.repo.create_session(req)
    background_tasks.add_task(run_prep_for_session, session_id, req, deps)
    return PrepResponse(session_id=session_id)
