"""``POST /api/score`` — score a completed interview session."""

from __future__ import annotations

from fastapi import APIRouter

from ..core.deps import build_deps
from ..post import run_score
from ..shared_models import ScoreRequest, ScoreResponse

router = APIRouter()


@router.post("/api/score", response_model=ScoreResponse)
async def score(req: ScoreRequest) -> ScoreResponse:
    scorecard = await run_score(req, build_deps())
    return ScoreResponse(session_id=req.session_id, scorecard=scorecard)
