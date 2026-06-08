"""Specialist interviewer personas reachable via native LiveKit handoffs.

REQUIRES the optional ``livekit-agents`` extra (``uv sync --extra livekit``);
this module imports ``livekit.agents`` at load time and must NOT be imported by
``live/__init__.py`` (keep the offline ``import ...live.state`` path clean).

Each persona is a lean :class:`~livekit.agents.Agent` with its own short
instructions and may override the per-agent LLM/TTS (e.g. a more deliberate
voice for a coding round). The shared interview tools (save_answer,
get_next_question, ...) live on the base :class:`Interviewer` agent; returning
one of these from a ``@function_tool`` performs a native persona handoff while
keeping the same :class:`AgentSession` userdata.
"""

from __future__ import annotations

from livekit.agents import Agent

_CODING_INSTRUCTIONS = (
    "You are now running the CODING round. Pose one focused, hands-on problem "
    "tied to the candidate's stack. Ask them to think aloud; nudge with a single "
    "hint if they stall. Do not lecture. When the problem is resolved or time is "
    "tight, call save_answer then get_next_question."
)

_BEHAVIORAL_INSTRUCTIONS = (
    "You are now running the BEHAVIORAL round. Ask one STAR-style question at a "
    "time about real past experience. Listen, then ask exactly one probing "
    "follow-up for specifics (the 'I' not the 'we'). Then call save_answer and "
    "get_next_question. Warm, concise, never leading."
)


class CodingRoundAgent(Agent):
    """Persona for the live coding round."""

    def __init__(self) -> None:
        super().__init__(instructions=_CODING_INSTRUCTIONS)


class BehavioralAgent(Agent):
    """Persona for the behavioral round."""

    def __init__(self) -> None:
        super().__init__(instructions=_BEHAVIORAL_INSTRUCTIONS)
