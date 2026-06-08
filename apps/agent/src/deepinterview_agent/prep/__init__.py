"""WP-6 prep pipeline: the LangGraph that turns a ``PrepRequest`` into a
persisted, ready-to-interview ``InterviewContext``.

Public entry point is :func:`run_prep`, whose signature is the stable contract
the API layer and tests depend on::

    async def run_prep(req: PrepRequest, deps: Deps) -> str

It creates a session, runs the prep graph (CV/JD/company research fan-out → gap
analysis → question planning), assembles and persists the ``InterviewContext``,
marks the session ``ready``, and returns the ``session_id``. Any failure marks
the session ``error`` and re-raises.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.logging import get_logger
from ..core.validation import validate_prep_inputs
from ..shared_models import InterviewContext
from .graph import build_prep_graph
from .nodes import fetch_cv

if TYPE_CHECKING:
    from ..core.deps import Deps
    from ..shared_models import PrepRequest

__all__ = ["run_prep", "run_prep_for_session", "build_prep_graph"]

log = get_logger(__name__)


async def run_prep(req: PrepRequest, deps: Deps) -> str:
    """Run the prep pipeline inline and return the new ``session_id``.

    Stable contract for tests / skilllib: creates a session then runs the
    pipeline synchronously on it. The session ends ``ready`` (or ``rejected`` for
    wholly meaningless input, or ``error`` if no plan could be produced).
    """
    session_id = await deps.repo.create_session(req)
    await run_prep_for_session(session_id, req, deps)
    return session_id


async def run_prep_for_session(
    session_id: str, req: PrepRequest, deps: Deps
) -> None:
    """Run the prep pipeline against an EXISTING session row.

    Validates inputs first (after fetching the CV so the resolved document text
    is judged), then runs the graph, persists the ``InterviewContext`` and marks
    the session ``ready``. Wholly meaningless input → ``rejected`` (no graph, no
    LLM). A pipeline that cannot produce a plan → ``error``. Never raises: this is
    designed to run as a fire-and-forget background task.
    """
    try:
        # Resolve the CV document first so validation can judge real content.
        fetched = await fetch_cv({"req": req}, deps)
        cv_text = fetched.get("cv_text", req.cv_url)

        ok, warnings = validate_prep_inputs(req, cv_text=cv_text)
        if warnings:
            await deps.repo.add_warnings(session_id, warnings)

        if not ok:
            # Wholly meaningless CV + JD: reject without spending a model call.
            await deps.repo.update_status(session_id, "rejected")
            return

        # A junk company is a warning (not a rejection); signal the graph to skip
        # company research so we don't fabricate intel or waste calls.
        company_ok = not any("company name" in w for w in warnings)

        graph = build_prep_graph(deps)
        result = await graph.ainvoke(
            {
                "req": req,
                "session_id": session_id,
                "cv_text": cv_text,
                "company_ok": company_ok,
            }
        )

        ctx = InterviewContext(
            session_id=session_id,
            candidate=result["candidate"],
            job=result["job"],
            company=result["company"],
            gap=result["gap"],
            plan=result["plan"],
            cursor=0,
            answers=[],
            scorecard=None,
        )

        await deps.repo.save_context(session_id, ctx)
        await deps.repo.update_status(session_id, "ready")
    except Exception as exc:  # noqa: BLE001 - background task: record, don't propagate
        log.exception("run_prep_for_session(%s) failed: %s", session_id, exc)
        try:
            await deps.repo.update_status(session_id, "error")
        except Exception:  # noqa: BLE001 - best-effort status write
            log.warning("could not mark session %s as error", session_id)
