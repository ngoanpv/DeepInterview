"""Spoken Study Coach persona for the live voice stack (voice sub-phase of WP-4).

REQUIRES the optional ``livekit-agents`` extra (``uv sync --extra livekit``);
this module imports ``livekit.agents`` at load time and must NOT be imported by
``live/__init__.py`` (keep the offline ``import ...live.state`` path clean). It is
imported lazily by ``worker_coach.py``.

The :class:`CoachAgent` is a lean :class:`~livekit.agents.Agent` that runs a
Socratic, spoken coaching session. The heavy planning (scorecard -> StudyPlan,
grounded chat synthesis) stays in the OFFLINE ``coach/`` module; this persona only
carries the live turn loop. It deliberately wires NO retrieval tool onto the turn
path — grounded coaching is the latency-tolerant offline ``/api/coach/chat`` route's
job, not the live loop's.

The instructions string is built by the livekit-free
:func:`deepinterview_agent.coach.prompts.coach_agent_instructions`, so the persona
text is unit-testable without the livekit extra.
"""

from __future__ import annotations

from livekit.agents import Agent

from ..coach.prompts import coach_agent_instructions


class CoachAgent(Agent):
    """A spoken, Socratic interview-prep coach persona.

    Args:
        weak_areas_summary: A short, already-built summary of the candidate's
            weak competencies / scorecard context (see
            :func:`deepinterview_agent.live.state.weak_areas_summary`). Injected
            verbatim into the instructions so the live prompt stays lean.
        lang: Primary language to coach in.
    """

    def __init__(self, *, weak_areas_summary: str, lang: str = "en") -> None:
        super().__init__(
            instructions=coach_agent_instructions(weak_areas_summary, lang),
        )
