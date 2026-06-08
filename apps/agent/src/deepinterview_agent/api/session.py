"""``GET /api/session/{session_id}`` — live prep progress + the session view.

Returns a :class:`SessionView` (status, completed prep steps, input-quality
warnings, and the :class:`InterviewContext` once ready). Unknown ids → 404.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..core.deps import build_deps
from .views import SessionView

router = APIRouter()


@router.get("/api/session/{session_id}", response_model=SessionView)
async def get_session(session_id: str) -> SessionView:
    view = await build_deps().repo.get_session_view(session_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Unknown session_id")
    return view
