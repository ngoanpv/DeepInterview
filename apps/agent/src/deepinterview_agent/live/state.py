"""Pure, livekit-free state machine for the live interview loop.

This module is the testable heart of WP-5. It deliberately imports NOTHING from
``livekit`` so it works with the optional ``livekit-agents`` extra absent — the
worker and agent personas (``interviewer``/``handoffs``/``director``) wrap these
functions but live in livekit-coupled modules.

:class:`InterviewUserdata` is the per-session state carried through the call. The
``InterviewContext`` it wraps owns the authoritative cursor (``ctx.cursor``) and
answer log (``ctx.answers``); the functions below are thin, deterministic
operations over it. The ``transcript`` field is a flat running log of turns the
worker persists on shutdown. Timestamps are caller-supplied ISO-8601 strings
(see :class:`deepinterview_agent.shared_models.AnswerRecord`); nothing here reads
the clock or uses randomness, so it is fully reproducible in tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..shared_models import AnswerRecord

if TYPE_CHECKING:
    from ..shared_models import InterviewContext, PlannedQuestion, Section


@dataclass
class InterviewUserdata:
    """Mutable per-session state for one live interview.

    ``ctx`` is the source of truth (cursor + answers live on it). ``transcript``
    is a flat ``[{"role", "text"}]`` log the worker flushes on shutdown.
    """

    ctx: InterviewContext
    session_id: str
    transcript: list[dict] = field(default_factory=list)


def current_question(ud: InterviewUserdata) -> PlannedQuestion | None:
    """Return the question at the current cursor, or ``None`` if past the end."""
    questions = ud.ctx.plan.questions
    cursor = ud.ctx.cursor
    if 0 <= cursor < len(questions):
        return questions[cursor]
    return None


def current_section(ud: InterviewUserdata) -> Section | None:
    """Return the section of the current question, or ``None`` if past the end."""
    q = current_question(ud)
    return q.section if q is not None else None


def advance(ud: InterviewUserdata) -> None:
    """Move the cursor forward by one question (may land past the end)."""
    ud.ctx.cursor += 1


def is_complete(ud: InterviewUserdata) -> bool:
    """True once the cursor has moved past the last planned question."""
    return ud.ctx.cursor >= len(ud.ctx.plan.questions)


def save_answer(
    ud: InterviewUserdata,
    *,
    transcript: str,
    started_at: str,
    ended_at: str,
) -> AnswerRecord:
    """Record the candidate's answer to the *current* question.

    Appends a new :class:`AnswerRecord` (keyed by the current question's id) to
    ``ud.ctx.answers`` and returns it. No-ops to a synthetic record only when the
    cursor is past the end; callers should normally have a current question.
    """
    q = current_question(ud)
    question_id = q.id if q is not None else ""
    record = AnswerRecord(
        question_id=question_id,
        transcript=transcript,
        started_at=started_at,
        ended_at=ended_at,
    )
    ud.ctx.answers.append(record)
    return record


def next_section(ud: InterviewUserdata) -> PlannedQuestion | None:
    """Advance the cursor to the first question whose section differs from the
    current one, and return it (or ``None`` if there is no later section).

    Skips the remainder of the current section. If already past the end, the
    cursor is left at the end and ``None`` is returned.
    """
    questions = ud.ctx.plan.questions
    starting_section = current_section(ud)

    # Already past the end -> nothing to advance to.
    if starting_section is None:
        ud.ctx.cursor = len(questions)
        return None

    cursor = ud.ctx.cursor
    while cursor < len(questions) and questions[cursor].section == starting_section:
        cursor += 1
    ud.ctx.cursor = cursor
    return questions[cursor] if cursor < len(questions) else None


def add_turn(ud: InterviewUserdata, role: str, text: str) -> None:
    """Append a turn to the flat running transcript log."""
    ud.transcript.append({"role": role, "text": text})


def compact_summary(ud: InterviewUserdata) -> str:
    """A short candidate summary string for the lean live prompt.

    Combines the role/level being interviewed for with the precomputed 120-word
    candidate summary. Intentionally compact: the live prompt injects ONLY this
    plus the current question and recent turns — never the whole CV/JD/company.
    """
    cand = ud.ctx.candidate
    job = ud.ctx.job
    role = f"{job.title} ({job.seniority}) at {job.company_name}"
    return (
        f"Candidate: {cand.name}, {cand.headline}. "
        f"Interviewing for: {role}. "
        f"{cand.summary_120w}"
    )
