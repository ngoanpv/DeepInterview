"""The base live interviewer :class:`Agent` and its turn-path tools.

REQUIRES the optional ``livekit-agents`` extra (``uv sync --extra livekit``);
imports ``livekit.agents`` at load time, so it is imported lazily by the worker
and NOT by ``live/__init__.py`` (offline ``import ...live.state`` stays clean).

Design rules (CLAUDE.md golden rule #2: keep the live loop lean):
- The prompt injects ONLY the compact candidate summary + the current question +
  recent turns — never the whole CV / JD / company intel.
- ``@function_tool`` methods mutate the local :class:`InterviewUserdata` ONLY.
  No network / DB on the turn path; persistence + scoring happen on shutdown
  (see ``worker.py``).
- Handoffs return a fresh persona agent (``CodingRoundAgent`` / ``BehavioralAgent``)
  to switch styles natively while keeping the same session userdata.
"""

from __future__ import annotations

from livekit.agents import Agent, RunContext, function_tool

from . import state
from .handoffs import BehavioralAgent, CodingRoundAgent
from .state import InterviewUserdata


def _localized(text: dict[str, str], primary: str) -> str:
    """Resolve a ``LocalizedText`` to the primary language, falling back to en."""
    return text.get(primary) or text.get("en") or next(iter(text.values()), "")


def _wrap_signal() -> str:
    return "INTERVIEW_COMPLETE: thank the candidate warmly and end the interview."


def build_instructions(ud: InterviewUserdata) -> str:
    """Lean per-question system prompt: compact summary + current question."""
    primary = ud.ctx.plan.language_mode.primary
    summary = state.compact_summary(ud)
    q = state.current_question(ud)
    question_line = (
        _localized(q.text, primary) if q is not None else "(no further questions)"
    )
    return (
        "You are a senior, friendly technical interviewer running a real-time "
        "voice mock interview. Speak naturally and concisely.\n\n"
        f"{summary}\n\n"
        f"Primary language: {primary}.\n"
        f"Current question to ask: {question_line}\n\n"
        "Ask this one question, listen to the full answer, then ask at most one "
        "light follow-up. When the answer is complete, call save_answer with the "
        "candidate's answer, then call get_next_question to proceed. Use "
        "next_section to move to a different round, request_clarification only if "
        "the candidate seems confused. Never read the rubric aloud."
    )


class Interviewer(Agent):
    """The primary interviewer persona; owns the shared interview tools."""

    def __init__(self, userdata: InterviewUserdata) -> None:
        super().__init__(instructions=build_instructions(userdata))

    @function_tool
    async def save_answer(
        self,
        context: RunContext[InterviewUserdata],
        answer: str,
        started_at: str = "",
        ended_at: str = "",
    ) -> str:
        """Record the candidate's answer to the current question.

        Call this once the candidate has finished answering, BEFORE
        get_next_question. ``answer`` is the candidate's spoken answer text.
        """
        ud = context.userdata
        state.add_turn(ud, "user", answer)
        record = state.save_answer(
            ud, transcript=answer, started_at=started_at, ended_at=ended_at
        )
        return f"Saved answer for question {record.question_id}."

    @function_tool
    async def get_next_question(self, context: RunContext[InterviewUserdata]) -> str:
        """Advance to the next planned question and return it (or a wrap signal)."""
        ud = context.userdata
        state.advance(ud)
        if state.is_complete(ud):
            return _wrap_signal()
        q = state.current_question(ud)
        assert q is not None  # not complete -> a current question exists
        primary = ud.ctx.plan.language_mode.primary
        text = _localized(q.text, primary)
        state.add_turn(ud, "assistant", text)
        return f"Next question ({q.section}): {text}"

    @function_tool
    async def next_section(self, context: RunContext[InterviewUserdata]) -> str:
        """Skip to the first question of the next section (or wrap if none)."""
        ud = context.userdata
        q = state.next_section(ud)
        if q is None:
            return _wrap_signal()
        primary = ud.ctx.plan.language_mode.primary
        text = _localized(q.text, primary)
        state.add_turn(ud, "assistant", text)
        return f"Moving to {q.section}: {text}"

    @function_tool
    async def get_difficulty_hint(
        self, context: RunContext[InterviewUserdata]
    ) -> str:
        """Advisory hint on whether to go harder/easier, advance, or wrap.

        OPTIONAL and non-binding: consult it only if you're unsure how to pace the
        current section. It is computed locally from answers already given (no
        network, no blocking) and never changes the question cursor.
        """
        return state.difficulty_hint(context.userdata)

    @function_tool
    async def request_clarification(
        self, context: RunContext[InterviewUserdata], reason: str = ""
    ) -> str:
        """Note that the candidate needs the current question rephrased."""
        ud = context.userdata
        q = state.current_question(ud)
        if q is None:
            return "No active question to clarify."
        primary = ud.ctx.plan.language_mode.primary
        return (
            "Rephrase the current question more simply, keeping the same intent: "
            f"{_localized(q.text, primary)}"
        )

    @function_tool
    async def start_coding_round(
        self, context: RunContext[InterviewUserdata]
    ) -> CodingRoundAgent:
        """Hand off to the coding-round persona (native LiveKit agent handoff)."""
        return CodingRoundAgent()

    @function_tool
    async def start_behavioral_round(
        self, context: RunContext[InterviewUserdata]
    ) -> BehavioralAgent:
        """Hand off to the behavioral-round persona (native LiveKit agent handoff)."""
        return BehavioralAgent()
