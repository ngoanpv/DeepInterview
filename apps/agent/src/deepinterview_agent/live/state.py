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
from typing import TYPE_CHECKING, Literal

from ..shared_models import AnswerRecord

if TYPE_CHECKING:
    from ..shared_models import InterviewContext, PlannedQuestion, Section

# A directional hint the live model MAY consider when adapting question depth.
# Purely advisory: nothing here moves the cursor or mutates interview state.
Recommendation = Literal["harder", "easier", "advance", "wrap"]

# Deterministic answer-substance thresholds (word counts of the saved answer
# transcript). Mid-call we have no rubric scores yet, so substance is the
# strongest reproducible signal of how the candidate is coping with the section.
_THIN_WORDS = 12
_RICH_WORDS = 80
# Planned difficulty is on the documented 1-5 band; only suggest "harder" when
# there is a higher rung left to climb to.
_MAX_DIFFICULTY = 5


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


# --- adaptive difficulty (pure, livekit-free, deterministic) -----------------


@dataclass(frozen=True)
class DifficultySignal:
    """An advisory read of how the candidate is doing in the *current* section.

    Fully derived from the plan + cursor + answer log; never mutates anything.
    ``recommendation`` is the directional hint; ``rationale`` is a short, lean
    string suitable for handing to the live model.
    """

    recommendation: Recommendation
    section: Section | None
    answered_in_section: int
    section_size: int
    avg_answer_words: float
    current_difficulty: int
    rationale: str


def _answers_by_question_id(ud: InterviewUserdata) -> dict[str, AnswerRecord]:
    """Last saved answer per question id (later answers win)."""
    by_id: dict[str, AnswerRecord] = {}
    for a in ud.ctx.answers:
        by_id[a.question_id] = a
    return by_id


def _word_count(text: str) -> int:
    return len(text.split())


def evaluate_difficulty(ud: InterviewUserdata) -> DifficultySignal:
    """Recommend a difficulty move for the current section. PURE + deterministic.

    Reads only ``ud.ctx.plan.questions``, ``ud.ctx.cursor`` and ``ud.ctx.answers``
    — it NEVER touches the cursor or appends anything. The heuristic looks at the
    answers already given within the *current* section and compares their average
    substance (word count) against fixed thresholds:

    * past the end, or in the terminal ``wrap`` section  -> ``"wrap"``
    * no answers in the section yet                      -> ``"advance"`` (neutral)
    * thin answers                                       -> ``"easier"``
    * rich answers with a higher difficulty rung left    -> ``"harder"``
    * otherwise (section solidly covered / maxed out)    -> ``"advance"``
    """
    section = current_section(ud)
    if section is None or section == "wrap":
        return DifficultySignal(
            recommendation="wrap",
            section=section,
            answered_in_section=0,
            section_size=0,
            avg_answer_words=0.0,
            current_difficulty=0,
            rationale=(
                "Past the planned questions — wrap up."
                if section is None
                else "In the wrap section — bring the interview to a close."
            ),
        )

    questions = ud.ctx.plan.questions
    section_qs = [q for q in questions if q.section == section]
    section_size = len(section_qs)
    by_id = _answers_by_question_id(ud)
    answered = [
        by_id[q.id] for q in section_qs if q.id in by_id
    ]
    answered_in_section = len(answered)

    current = current_question(ud)
    current_difficulty = current.difficulty if current is not None else 0

    if answered_in_section == 0:
        # No evidence yet this section; keep the interview on plan.
        return DifficultySignal(
            recommendation="advance",
            section=section,
            answered_in_section=0,
            section_size=section_size,
            avg_answer_words=0.0,
            current_difficulty=current_difficulty,
            rationale=(
                f"No answers yet in the {section} section — proceed as planned."
            ),
        )

    total_words = sum(_word_count(a.transcript) for a in answered)
    avg_words = total_words / answered_in_section

    if avg_words < _THIN_WORDS:
        rec: Recommendation = "easier"
        rationale = (
            f"Answers in the {section} section are thin "
            f"(~{avg_words:.0f} words) — ease off and ask something more concrete."
        )
    elif avg_words > _RICH_WORDS and current_difficulty < _MAX_DIFFICULTY:
        rec = "harder"
        rationale = (
            f"Answers in the {section} section are strong "
            f"(~{avg_words:.0f} words) — push to a harder, deeper question."
        )
    else:
        rec = "advance"
        rationale = (
            f"The {section} section is well covered "
            f"({answered_in_section}/{section_size} answered) — move on."
        )

    return DifficultySignal(
        recommendation=rec,
        section=section,
        answered_in_section=answered_in_section,
        section_size=section_size,
        avg_answer_words=avg_words,
        current_difficulty=current_difficulty,
        rationale=rationale,
    )


def difficulty_hint(ud: InterviewUserdata) -> str:
    """A lean one-line hint string for the live model: ``"<rec>: <rationale>"``."""
    sig = evaluate_difficulty(ud)
    return f"{sig.recommendation}: {sig.rationale}"


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
