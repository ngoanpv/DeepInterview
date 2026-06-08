"""Async node functions for the WP-6 prep graph.

Every node takes ``(state, deps)`` and returns a partial ``PrepState`` dict with
only the key(s) it computes; LangGraph merges those into the running state. Deps
are injected into the graph via :func:`functools.partial` (see ``graph.py``), so
each compiled node presents the ``(state)`` signature LangGraph expects.

``fetch_cv`` is deliberately best-effort and offline-tolerant: any failure to
GET the CV URL (DNS error, timeout, non-2xx, malformed URL) falls back to using
the URL string itself as the document text. This keeps the whole pipeline — and
the existing ``POST /api/prep`` test that points at an unreachable example.com —
green without network access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from ..core.adapters.mock import build_mock
from ..core.logging import get_logger
from ..shared_models import (
    CandidateProfile,
    Citation,
    CompanyIntel,
    GapAnalysis,
    JobSpec,
    QuestionPlan,
)
from .prompts import (
    company_research_prompts,
    cv_analysis_prompts,
    gap_matching_prompts,
    jd_analysis_prompts,
    language_name,
    question_planner_prompts,
)
from .state import PrepState

if TYPE_CHECKING:
    from ..core.deps import Deps

log = get_logger(__name__)

# Keep the CV fetch tight so an unreachable host fails fast offline.
_CV_FETCH_TIMEOUT_SEC = 5.0


async def _mark(state: PrepState, deps: Deps, step: str) -> None:
    """Record that ``step`` finished, if running against a known session.

    Best-effort: a missing/closed session must never crash prep — the progress
    signal is for the UI only.
    """
    session_id = state.get("session_id")
    if not session_id:
        return
    try:
        await deps.repo.mark_progress(session_id, step)
    except Exception as exc:  # noqa: BLE001 - progress is advisory only
        log.warning("mark_progress(%s) failed (%s)", step, exc)


async def _warn(state: PrepState, deps: Deps, warnings: list[str]) -> None:
    """Attach input-quality/fallback warnings to the session (best-effort)."""
    session_id = state.get("session_id")
    if not session_id or not warnings:
        return
    try:
        await deps.repo.add_warnings(session_id, warnings)
    except Exception as exc:  # noqa: BLE001 - warnings are advisory only
        log.warning("add_warnings failed (%s)", exc)


async def fetch_cv(state: PrepState, deps: Deps) -> PrepState:
    """Best-effort fetch of the CV document; fall back to the URL string.

    Idempotent: if ``cv_text`` is already in state (the caller pre-fetched it so
    it could validate inputs), this is a no-op — we never fetch the CV twice.
    """
    if state.get("cv_text"):
        return {}
    req = state["req"]
    cv_text = req.cv_url
    try:
        async with httpx.AsyncClient(timeout=_CV_FETCH_TIMEOUT_SEC) as client:
            resp = await client.get(req.cv_url, follow_redirects=True)
            resp.raise_for_status()
            text = resp.text
            if text.strip():
                cv_text = text
    except Exception as exc:  # noqa: BLE001 - best-effort: any failure -> fallback
        log.warning("fetch_cv: using cv_url as document text (%s)", exc)
    return {"cv_text": cv_text}


async def cv_analysis(state: PrepState, deps: Deps) -> PrepState:
    """Extract a ``CandidateProfile`` from the fetched CV text."""
    system, user = cv_analysis_prompts(state["cv_text"])
    try:
        candidate = await deps.llm.complete_json(
            system=system, user=user, schema=CandidateProfile
        )
    except Exception as exc:  # noqa: BLE001 - resilient: degrade, don't crash prep
        log.warning("cv_analysis failed, using minimal profile (%s)", exc)
        candidate = build_mock(CandidateProfile)
        await _warn(state, deps, ["Could not analyze the CV; used a minimal profile."])
    await _mark(state, deps, "cv_analysis")
    return {"candidate": candidate}


async def jd_analysis(state: PrepState, deps: Deps) -> PrepState:
    """Extract a ``JobSpec`` from the job description text."""
    req = state["req"]
    system, user = jd_analysis_prompts(req.jd_text, req.company)
    try:
        job = await deps.llm.complete_json(system=system, user=user, schema=JobSpec)
    except Exception as exc:  # noqa: BLE001 - resilient: degrade, don't crash prep
        log.warning("jd_analysis failed, using minimal job spec (%s)", exc)
        job = build_mock(JobSpec)
        await _warn(
            state, deps, ["Could not analyze the job description; used a minimal spec."]
        )
    await _mark(state, deps, "jd_analysis")
    return {"job": job}


def _empty_company_intel(name: str) -> CompanyIntel:
    """A valid, empty ``CompanyIntel`` for a junk/unknown company (no fabrication)."""
    return CompanyIntel(
        name=name or "Unknown",
        summary="",
        industry=None,
        tech_stack=[],
        values=[],
        interview_process=[],
        recent_news=[],
        citations=[],
    )


async def company_research(state: PrepState, deps: Deps) -> PrepState:
    """Search the web for company interview intel and synthesize ``CompanyIntel``.

    If the company name was flagged junk (``company_ok`` is False) this skips all
    search + LLM work and returns an empty-but-valid intel, so we never fabricate
    company knowledge from a meaningless name or waste calls on it.
    """
    req = state["req"]
    company = req.company

    if not state.get("company_ok", True):
        log.info("company_research: skipping for junk company %r", company)
        await _mark(state, deps, "company_research")
        return {"company": _empty_company_intel(company)}

    primary = req.language_mode.primary

    queries: list[tuple[str, str]] = [(f"{company} interview process", "en")]
    if primary != "en":
        localized = f"{company} interview process {language_name(primary)}"
        queries.append((localized, primary))

    results = []
    for query, lang in queries:
        try:
            results.extend(await deps.search.search(query, lang=lang, max_results=4))
        except Exception as exc:  # noqa: BLE001 - search is best-effort
            log.warning("company_research: search failed for %r (%s)", query, exc)

    snippets = "\n".join(f"- {r.title}: {r.snippet}" for r in results) or "(no results)"
    system, user = company_research_prompts(company, snippets)
    try:
        intel = await deps.llm.complete_json(
            system=system, user=user, schema=CompanyIntel
        )
    except Exception as exc:  # noqa: BLE001 - resilient: degrade, don't crash prep
        log.warning("company_research failed, using minimal intel (%s)", exc)
        intel = _empty_company_intel(company)
        await _warn(
            state, deps, ["Could not research the company; proceeding without intel."]
        )

    citations = [
        Citation(title=r.title, url=r.url, snippet=r.snippet) for r in results
    ]
    intel = intel.model_copy(update={"citations": citations})
    await _mark(state, deps, "company_research")
    return {"company": intel}


async def gap_matching(state: PrepState, deps: Deps) -> PrepState:
    """Compare candidate vs job into a ``GapAnalysis`` (join of cv + jd)."""
    system, user = gap_matching_prompts(state["candidate"], state["job"])
    try:
        gap = await deps.llm.complete_json(
            system=system, user=user, schema=GapAnalysis
        )
    except Exception as exc:  # noqa: BLE001 - resilient: degrade, don't crash prep
        log.warning("gap_matching failed, using minimal analysis (%s)", exc)
        gap = build_mock(GapAnalysis)
        await _warn(state, deps, ["Could not compute the gap analysis; used a minimal one."])
    await _mark(state, deps, "gap_matching")
    return {"gap": gap}


def _skill_library_hint(company: str, role: str, level: str) -> str:
    """Compact summary of any matching live skill playbook (WP-10 retrieval).

    Best-effort and additive: any failure (missing/un-parseable library, import
    error) returns an empty string so prep never depends on the skill store.
    """
    try:
        from ..skilllib import find_relevant  # noqa: PLC0415 - optional, lazy

        skills = find_relevant(company=company, role=role, level=level)
        if not skills:
            return ""
        lines: list[str] = []
        for skill in skills[:2]:
            fm = skill.frontmatter
            lines.append(
                f"- {fm.company} {fm.role} ({fm.level}); competencies: "
                f"{', '.join(fm.competency) or 'n/a'}; "
                f"confidence {fm.confidence:.2f} from {fm.source_runs} run(s)"
            )
        return "\n".join(lines)
    except Exception:  # noqa: BLE001 - retrieval is strictly best-effort
        return ""


async def question_planner(state: PrepState, deps: Deps) -> PrepState:
    """Keystone: synthesize the full ``QuestionPlan`` from all upstream state."""
    req = state["req"]
    system, user = question_planner_prompts(
        candidate=state["candidate"],
        job=state["job"],
        company=state["company"],
        gap=state["gap"],
        language_mode=req.language_mode,
    )
    # WP-10: inject any matching distilled playbook as extra planner context.
    hint = _skill_library_hint(
        company=state["company"].name,
        role=state["job"].title,
        level=state["job"].seniority,
    )
    if hint:
        user = f"{user}\n\nKNOWN PLAYBOOK SIGNALS (from prior interviews):\n{hint}"
    try:
        plan = await deps.llm.complete_json(
            system=system, user=user, schema=QuestionPlan
        )
    except Exception as exc:  # noqa: BLE001 - keystone must still emit a valid plan
        log.warning("question_planner failed, using minimal generic plan (%s)", exc)
        plan = build_mock(QuestionPlan)
        await _warn(
            state, deps, ["Could not tailor the question plan; used a generic one."]
        )
    # Pin the language mode to the request so the live loop routes voice correctly,
    # regardless of what the model echoed back.
    plan = plan.model_copy(update={"language_mode": req.language_mode})
    await _mark(state, deps, "question_planner")
    return {"plan": plan}
