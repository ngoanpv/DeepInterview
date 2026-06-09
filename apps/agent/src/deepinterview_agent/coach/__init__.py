"""WP-4 Study Coach: scorecard -> study plan, and grounded tutoring chat.

Sequential async (no LangGraph), mirrors ``post/``. ``run_coach_plan`` turns a
``ScoreCard``'s ``weak_competencies`` into a ``StudyPlan`` (one module per weak
competency, weakest-first); ``run_coach_chat`` answers a learner question
grounded in ``deps.knowledge`` then synthesized by the LLM. Every LLM/retrieval
call is guarded with a timeout + fallback so the Prep Coach UI always gets a
valid response.

``run_coach_plan`` takes the ``ScoreCard`` directly (the client already holds it
from the report) rather than a ``session_id`` — the coach plan is a pure function
of the scorecard, so it needs no repo/storage lookup.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from ..core.logging import get_logger
from ..shared_models import CoachReply, StudyModule, StudyPlan
from .prompts import coach_chat_prompts, study_module_prompts

if TYPE_CHECKING:
    from ..core.deps import Deps
    from ..shared_models import CoachChatRequest, MasteryState, ScoreCard

log = get_logger(__name__)

__all__ = ["run_coach_plan", "run_coach_chat"]

_DEFAULT_EST_MIN = 25
_STAGE_TIMEOUT = 60.0


class _ModuleDraft(BaseModel):
    """LLM-authored fields for one study module; the rest is pinned deterministically."""

    model_config = ConfigDict(extra="forbid")
    title: str
    rationale: str
    est_min: int


class _ChatDraft(BaseModel):
    """LLM-authored fields for a coach reply; citations come from retrieval."""

    model_config = ConfigDict(extra="forbid")
    answer: str
    follow_ups: list[str]


def _status_for_level(level: str) -> MasteryState:
    """Map a scoring band onto a study-module mastery state."""
    return "learning" if level == "developing" else "shaky"


def _clamp_min(value: int) -> int:
    """Keep a module's estimated minutes in a sane 5-90 range."""
    return max(5, min(90, int(value)))


async def _guarded(coro, *, label: str, timeout: float = _STAGE_TIMEOUT):
    """Await ``coro`` with a timeout; on ANY error return ``None`` (caller falls back)."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except Exception:  # noqa: BLE001 - the coach must always return something usable
        log.exception("coach: stage %r failed; degrading", label)
        return None


def _empty_plan(summary: str) -> StudyPlan:
    return StudyPlan(modules=[], summary=summary, total_min=0)


async def run_coach_plan(scorecard: ScoreCard, deps: Deps) -> StudyPlan:
    """Build a ``StudyPlan`` from a scorecard's weak competencies.

    One module per ``weak_competencies`` entry, ordered weakest-first; the LLM
    drafts the title/rationale/est_min while ``competency`` and ``status`` are
    pinned deterministically so the plan maps cleanly back onto the loop's
    shared competency space.
    """
    weak = list(scorecard.weak_competencies)
    if not weak:
        return _empty_plan(
            "No weak areas from your last interview — nice work. Run another mock to stay sharp."
        )

    score_by_comp = {cs.competency: cs for cs in scorecard.competency_scores}
    # Weakest (lowest score) first; competencies absent from the scores sort last.
    weak.sort(key=lambda c: score_by_comp[c].score if c in score_by_comp else 99.0)

    modules: list[StudyModule] = []
    for i, comp in enumerate(weak, start=1):
        cs = score_by_comp.get(comp)
        evidence = cs.evidence if cs is not None else ""
        level = cs.level if cs is not None else "weak"
        system, user = study_module_prompts(comp, evidence, level)
        draft = await _guarded(
            deps.llm.complete_json(system=system, user=user, schema=_ModuleDraft),
            label=f"module:{comp}",
        )
        if draft is None:
            draft = _ModuleDraft(
                title=f"Strengthen {comp}",
                rationale="A focus area flagged by your last interview.",
                est_min=_DEFAULT_EST_MIN,
            )
        modules.append(
            StudyModule(
                id=f"m{i}",
                title=draft.title,
                competency=comp,
                status=_status_for_level(level),
                est_min=_clamp_min(draft.est_min),
                rationale=draft.rationale,
            )
        )

    total = sum(m.est_min for m in modules)
    plural = "s" if len(modules) != 1 else ""
    summary = f"{len(modules)} focus area{plural} from your last interview, about {total} min."
    return StudyPlan(modules=modules, summary=summary, total_min=total)


async def run_coach_chat(req: CoachChatRequest, deps: Deps) -> CoachReply:
    """Answer a learner question; ground + cite ONLY when a real KB is configured.

    Grounding (and therefore citations) is opt-in via ``LIGHTRAG_URL``. With no
    real retrieval backend (the default), we answer with the LLM and return NO
    citations rather than fabricating sources over an ungrounded answer.
    """
    if deps.settings.lightrag_url:
        grounded = await _guarded(
            deps.knowledge.search(req.session_id, req.query, req.lang),
            label="knowledge",
        )
        context, citations = grounded if grounded is not None else ("", [])
    else:
        context, citations = "", []

    system, user = coach_chat_prompts(req.query, context, req.lang)
    draft = await _guarded(
        deps.llm.complete_json(system=system, user=user, schema=_ChatDraft),
        label="chat",
    )
    if draft is None:
        return CoachReply(
            answer="I couldn't put together a coached answer just now — try asking again in a moment.",
            citations=citations,
            follow_ups=[],
        )
    return CoachReply(answer=draft.answer, citations=citations, follow_ups=draft.follow_ups[:3])
