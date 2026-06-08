"""API-only view models (not part of the wire contract in ``packages/shared``).

``SessionView`` is the read model behind ``GET /api/session/{id}``. It deliberately
lives here — NOT in ``shared_models`` — so the TS↔Pydantic parity check stays
untouched. It reports live prep progress (which agents have finished), any
input-quality warnings, and the assembled :class:`InterviewContext` once ready.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..shared_models import InterviewContext

__all__ = ["SessionView", "SessionStatus", "PROGRESS_STEPS"]

SessionStatus = Literal["prep", "ready", "rejected", "error"]

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
