"""Specialist interviewer personas reachable via native LiveKit handoffs.

REQUIRES the optional ``livekit-agents`` extra (``uv sync --extra livekit``);
this module imports ``livekit.agents`` (via ``interviewer``) at load time and
must NOT be imported by ``live/__init__.py`` (keep the offline
``import ...live.state`` path clean).

Each persona SUBCLASSES :class:`Interviewer` — in LiveKit Agents 1.x function
tools are per-agent, so a persona must inherit the shared interview tools
(save_answer, get_next_question, ...) or the model is ordered to call tools
that do not exist and the cursor/answer log silently stop advancing. The
handoff site passes the running ``chat_ctx`` so the persona keeps the
conversation history (a bare ``Agent`` starts from an empty context), and each
persona overrides ``on_enter`` to drive its round opening proactively — a
handoff that returns only an Agent generates no reply on its own.
"""

from __future__ import annotations

from . import state
from .interviewer import Interviewer, _localized

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


class _RoundPersona(Interviewer):
    """Shared base for round personas: full interview tools + a round opener."""

    _round_label = "next"

    def __init__(self, userdata, chat_ctx=None) -> None:  # noqa: ANN001
        super().__init__(
            userdata,
            chat_ctx=chat_ctx,
            extra_instructions=self._round_instructions(),
        )

    def _round_instructions(self) -> str:
        raise NotImplementedError

    async def on_enter(self) -> None:
        """Open the round proactively (no greeting — the interview is mid-flight)."""
        ud = self.session.userdata
        primary = ud.ctx.plan.language_mode.primary
        q = state.current_question(ud)
        question_line = (
            _localized(q.text, primary) if q is not None else "(no further questions)"
        )
        self.session.generate_reply(
            instructions=(
                f"Transition smoothly into the {self._round_label} round, speaking "
                f"in {primary}. In one short sentence say you're moving to this "
                f"round, then ask this question and stop: {question_line}. Do not "
                "re-introduce yourself or call any tools yet."
            )
        )


class CodingRoundAgent(_RoundPersona):
    """Persona for the live coding round."""

    _round_label = "coding"

    def _round_instructions(self) -> str:
        return _CODING_INSTRUCTIONS


class BehavioralAgent(_RoundPersona):
    """Persona for the behavioral round."""

    _round_label = "behavioral"

    def _round_instructions(self) -> str:
        return _BEHAVIORAL_INSTRUCTIONS
