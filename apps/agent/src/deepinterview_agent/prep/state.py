"""Shared state for the WP-6 prep ``StateGraph``.

``PrepState`` is the single channel dict threaded through every node. It is
``total=False`` so the graph can start from just ``{"req": ...}`` and each node
contributes the one (or few) keys it computes; LangGraph merges them across
supersteps. The final ``ainvoke`` result therefore carries every key below,
which :func:`deepinterview_agent.prep.run_prep` reads out to assemble the
``InterviewContext``.
"""

from __future__ import annotations

from typing import TypedDict

from ..shared_models import (
    CandidateProfile,
    CompanyIntel,
    GapAnalysis,
    JobSpec,
    PrepRequest,
    QuestionPlan,
)


class PrepState(TypedDict, total=False):
    """Mutable, additive state carried through the prep graph."""

    req: PrepRequest
    # Carried so nodes can report completion against an existing session row.
    session_id: str
    # False when the company name is junk -> company_research short-circuits.
    company_ok: bool
    cv_text: str
    candidate: CandidateProfile
    job: JobSpec
    company: CompanyIntel
    gap: GapAnalysis
    plan: QuestionPlan
