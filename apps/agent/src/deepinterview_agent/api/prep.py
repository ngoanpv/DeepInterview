"""``POST /api/prep`` — kick off the prep pipeline for a CV + JD + company.

Returns immediately with a ``session_id`` (status ``prep``); the heavy pipeline
runs in a FastAPI ``BackgroundTask`` and the client polls ``GET /api/session/{id}``
for progress + the final context. (Under Starlette's ``TestClient`` the background
task runs to completion before the response is returned.)
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from ..core.deps import build_deps
from ..prep import run_prep_for_session
from ..shared_models import PrepRequest, PrepResponse

router = APIRouter()

# Route-level size ceilings (Starlette imposes NO default body limit). Enforced
# here rather than as max_length on the shared contract models so the generated
# JSON Schemas stay in TS<->Pydantic parity. cv_url is generous because the
# offline path sends the whole CV as pasted text / a data: URL in this field.
_MAX_CV_URL_LEN = 2_000_000  # ~1.5MB data-URL CV
_MAX_JD_LEN = 200_000
_MAX_COMPANY_LEN = 500


@router.post("/api/prep", response_model=PrepResponse)
async def prep(req: PrepRequest, background_tasks: BackgroundTasks) -> PrepResponse:
    if (
        len(req.cv_url) > _MAX_CV_URL_LEN
        or len(req.jd_text) > _MAX_JD_LEN
        or len(req.company) > _MAX_COMPANY_LEN
    ):
        raise HTTPException(status_code=413, detail="CV/JD/company input too large")
    deps = build_deps()
    session_id = await deps.repo.create_session(req)
    background_tasks.add_task(run_prep_for_session, session_id, req, deps)
    return PrepResponse(session_id=session_id)
