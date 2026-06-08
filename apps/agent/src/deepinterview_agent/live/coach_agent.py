"""Spoken Study Coach persona for the live voice stack (voice sub-phase of WP-4).

REQUIRES the optional ``livekit-agents`` extra (``uv sync --extra livekit``);
this module imports ``livekit.agents`` at load time and must NOT be imported by
``live/__init__.py`` (keep the offline ``import ...live.state`` path clean). It is
imported lazily by ``worker_coach.py``.

The :class:`CoachAgent` is a lean :class:`~livekit.agents.Agent` that runs a
Socratic, spoken coaching session. The heavy planning (scorecard -> StudyPlan,
grounded chat synthesis) stays in the OFFLINE ``coach/`` module; this persona only
carries the live turn loop and, when enabled, a single ``search_knowledge_base``
function tool (reused from ``live/kb_tool.py``) so it can ground answers in the
candidate's prep materials via ``deps.knowledge``.

The instructions string is built by the livekit-free
:func:`deepinterview_agent.coach.prompts.coach_agent_instructions`, so the persona
text is unit-testable without the livekit extra.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from livekit.agents import Agent

from ..coach.prompts import coach_agent_instructions
from .kb_tool import make_search_knowledge_base

if TYPE_CHECKING:
    from ..core.adapters.knowledge import KnowledgeClient


class CoachAgent(Agent):
    """A spoken, Socratic interview-prep coach persona.

    Args:
        weak_areas_summary: A short, already-built summary of the candidate's
            weak competencies / scorecard context (see
            :func:`deepinterview_agent.live.state.weak_areas_summary`). Injected
            verbatim into the instructions so the live prompt stays lean.
        lang: Primary language to coach in.
        knowledge: Optional grounded-retrieval client. When provided, the agent
            gets a ``search_knowledge_base`` function tool bound to this client so
            it can look up the candidate's prep notes mid-conversation.
        user_id: The id used to scope knowledge lookups (typically the session id).
    """

    def __init__(
        self,
        *,
        weak_areas_summary: str,
        lang: str = "en",
        knowledge: KnowledgeClient | None = None,
        user_id: str = "",
    ) -> None:
        tools = []
        if knowledge is not None:
            # Reuse the live KB function tool (RAG-delay filler pattern lives there).
            tools.append(make_search_knowledge_base(knowledge, user_id, lang))
        super().__init__(
            instructions=coach_agent_instructions(weak_areas_summary, lang),
            tools=tools,
        )
