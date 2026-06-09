"""API-only view models (not part of the wire contract in ``packages/shared``).

``SessionView`` is the read model behind ``GET /api/session/{id}``. It deliberately
lives here — NOT in ``shared_models`` — so the TS↔Pydantic parity check stays
untouched. It reports live prep progress (which agents have finished), any
input-quality warnings, and the assembled :class:`InterviewContext` once ready.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..shared_models import InterviewContext, ScoreCard

__all__ = ["SessionView", "SessionStatus", "PROGRESS_STEPS"]

# "complete" is the terminal state set by the post-interview scoring step
# (see post/__init__.py); it must be a valid status or GET /api/session/{id}
# 500s on any read after an interview ends, blocking re-joins.
SessionStatus = Literal["prep", "ready", "rejected", "error", "complete"]

# The canonical ordered set of prep steps a session progresses through. Reported
# back as completed-step keys (a subset/permutation of these) in SessionView.
PROGRESS_STEPS: tuple[str, ...] = (
    "cv_analysis",
    "jd_analysis",
    "company_research",
    "gap_matching",
    "question_planner",
)


class SessionView(BaseModel):
    """Read model for a single session's status, progress and context."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    status: SessionStatus
    progress: list[str] = Field(default_factory=list)
    prep_warnings: list[str] = Field(default_factory=list)
    context: InterviewContext | None = None
    # The assembled scorecard once post-interview scoring has run (status
    # "complete"). Surfaced here so the web report can read it through the agent
    # API — no Supabase/RLS/auth on the read path (OSS runs without sign-in).
    scorecard: ScoreCard | None = None
