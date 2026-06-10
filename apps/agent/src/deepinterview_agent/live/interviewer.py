"""The base live interviewer :class:`Agent` and its turn-path tools.

REQUIRES the optional ``livekit-agents`` extra (``uv sync --extra livekit``);
imports ``livekit.agents`` at load time, so it is imported lazily by the worker
and NOT by ``live/__init__.py`` (offline ``import ...live.state`` stays clean).

Design rules (project golden rule #2: keep the live loop lean):
- The prompt injects ONLY the compact candidate summary + the current question +
  recent turns — never the whole CV / JD / company intel.
- ``@function_tool`` methods mutate the local :class:`InterviewUserdata` ONLY.
  No network / DB on the turn path; persistence + scoring happen on shutdown
  (see ``worker.py``).
- Handoffs return a fresh persona agent (``CodingRoundAgent`` / ``BehavioralAgent``)
  to switch styles natively while keeping the same session userdata. Personas
  subclass ``Interviewer`` (tools are per-agent in livekit-agents 1.x) and get
  the running ``chat_ctx`` so the conversation history survives the handoff.
- The flat ``ud.transcript`` log is fed by the worker's ``conversation_item_added``
  listener (real STT/agent turns) — tools no longer write to it, so answers are
  captured even when the model forgets to call ``save_answer``.
"""

from __future__ import annotations

from livekit.agents import Agent, RunContext, function_tool

from . import state
from .state import InterviewUserdata


def _localized(text: dict[str, str], primary: str) -> str:
    """Resolve a ``LocalizedText`` to the primary language, falling back to en."""
    return text.get(primary) or text.get("en") or next(iter(text.values()), "")


def _wrap_signal() -> str:
    return (
        "INTERVIEW_COMPLETE: thank the candidate warmly in one or two sentences, "
        "tell them their feedback report will be ready shortly, and then call "
        "end_interview to close the session."
    )


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

    def __init__(
        self,
        userdata: InterviewUserdata,
        *,
        chat_ctx=None,  # noqa: ANN001 - livekit ChatContext; optional extra absent offline
        extra_instructions: str = "",
    ) -> None:
        instructions = build_instructions(userdata)
        if extra_instructions:
            instructions = f"{instructions}\n\n{extra_instructions}"
        kwargs = {}
        if chat_ctx is not None:
            # Only forward when given: Agent distinguishes NOT_GIVEN from None.
            kwargs["chat_ctx"] = chat_ctx
        super().__init__(instructions=instructions, **kwargs)

    async def on_enter(self) -> None:
        """Open the interview proactively: greet the candidate and ask Q1.

        LiveKit calls this when the agent becomes the active speaker. Without it
        the agent stays silent until the candidate speaks first (the avatar sits
        on its idle loop). We drive the first turn with ``generate_reply``
        (synchronous in livekit-agents 1.x — returns a SpeechHandle) using the
        lean context already in the system prompt; subsequent turns flow through
        the tools. Round personas override this opener with a round transition
        (see ``handoffs.py``), so the greeting fires only for the base interviewer.
        """
        ud = self.session.userdata
        primary = ud.ctx.plan.language_mode.primary
        q = state.current_question(ud)
        question_line = (
            _localized(q.text, primary) if q is not None else "(no further questions)"
        )
        first_name = (ud.ctx.candidate.name or "there").split()[0]
        self.session.generate_reply(
            instructions=(
                f"Open the interview now, speaking in {primary}. Warmly greet the "
                f"candidate by first name ({first_name}) in one short sentence and "
                f"say you'll be running their mock interview for the {ud.ctx.job.title} "
                f"role at {ud.ctx.job.company_name}. Then ask this first question and "
                f"stop: {question_line}. Keep it natural and concise; do not call any "
                "tools yet."
            )
        )

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
        record = state.save_answer(
            ud, transcript=answer, started_at=started_at, ended_at=ended_at
        )
        return f"Saved answer for question {record.question_id}."

    async def _refresh_instructions(self, ud: InterviewUserdata) -> None:
        """Re-sync the system prompt with the advanced cursor (best-effort).

        Without this the prompt keeps saying "Current question to ask: <Q1>" for
        the whole interview, contradicting the tool-returned questions. Never
        allowed to break a turn.
        """
        try:
            await self.update_instructions(build_instructions(ud))
        except Exception:  # noqa: BLE001 - prompt refresh must never break a turn
            pass

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
        await self._refresh_instructions(ud)
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
        await self._refresh_instructions(ud)
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
    async def end_interview(self, context: RunContext[InterviewUserdata]) -> str:
        """End the interview session AFTER saying goodbye.

        Call this once you have thanked the candidate and said the report is on
        its way. It drains the current speech, then closes the session — which
        triggers the worker's persist + score shutdown path. Without it a
        finished interview idles until the hard duration guard trips.
        """
        try:
            self.session.shutdown(drain=True)
        except Exception:  # noqa: BLE001 - closing must never raise into the turn
            pass
        return "Interview ended. Say nothing further."

    @function_tool
    async def start_coding_round(self, context: RunContext[InterviewUserdata]) -> Agent:
        """Hand off to the coding-round persona (native LiveKit agent handoff)."""
        from .handoffs import CodingRoundAgent  # noqa: PLC0415 - personas subclass Interviewer

        return CodingRoundAgent(context.userdata, chat_ctx=self.chat_ctx)

    @function_tool
    async def start_behavioral_round(
        self, context: RunContext[InterviewUserdata]
    ) -> Agent:
        """Hand off to the behavioral-round persona (native LiveKit agent handoff)."""
        from .handoffs import BehavioralAgent  # noqa: PLC0415 - personas subclass Interviewer

        return BehavioralAgent(context.userdata, chat_ctx=self.chat_ctx)
