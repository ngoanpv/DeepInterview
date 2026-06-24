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


async def _ingest_prep_materials(
    session_id: str,
    req: PrepRequest,
    cv_text: str,
    ctx: InterviewContext,
    deps: Deps,
) -> None:
    """Ingest the prep documents (CV, JD, company intel) into the session's
    knowledge store, keyed by ``session_id``.

    Best-effort and self-contained: any knowledge failure is logged and
    swallowed so it can never turn a successful prep into an ``error``. With no
    knowledge sidecar configured the adapter is the offline mock (a no-op that
    returns a deterministic track id), so this stays free in the default flow.
    """
    files: list[str] = []
    if cv_text and cv_text.strip():
        files.append(f"CANDIDATE CV\n\n{cv_text.strip()}")
    if req.jd_text and req.jd_text.strip():
        files.append(f"JOB DESCRIPTION — {req.company}\n\n{req.jd_text.strip()}")

    company = ctx.company
    intel_parts: list[str] = []
    if company.summary:
        intel_parts.append(company.summary)
    if company.interview_process:
        intel_parts.append(
            "Interview process:\n- " + "\n- ".join(company.interview_process)
        )
    if company.recent_news:
        intel_parts.append("Recent news:\n- " + "\n- ".join(company.recent_news))
    if intel_parts:
        files.append(f"COMPANY INTEL — {company.name}\n\n" + "\n\n".join(intel_parts))

    if not files:
        return
    try:
        track_id = await deps.knowledge.ingest(session_id, files)
        log.info(
            "prep: ingested %d doc(s) into the knowledge store for session %s (track %s)",
            len(files),
            session_id,
            track_id,
        )
    except Exception as exc:  # noqa: BLE001 - knowledge ingest is strictly best-effort
        log.warning("prep: knowledge ingest failed for session %s (%s)", session_id, exc)


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
        # Parse the CV document first so validation judges the EXTRACTED text
        # (real prose from a PDF/DOCX), not the data:/URL pointer or raw bytes.
        # Pass session_id so any "couldn't read the CV" warning is persisted.
        fetched = await fetch_cv({"req": req, "session_id": session_id}, deps)
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

        # Close the WP-8 loop: ingest the prep materials into THIS session's
        # knowledge store so the Study Coach (which retrieves by session_id) can
        # ground answers in the candidate's CV/JD/company intel. Keyed by
        # session_id — the same key search() uses. Best-effort: never fail prep.
        await _ingest_prep_materials(session_id, req, cv_text, ctx, deps)
    except Exception as exc:  # noqa: BLE001 - background task: record, don't propagate
        log.exception("run_prep_for_session(%s) failed: %s", session_id, exc)
        try:
            await deps.repo.update_status(session_id, "error")
        except Exception:  # noqa: BLE001 - best-effort status write
            log.warning("could not mark session %s as error", session_id)
