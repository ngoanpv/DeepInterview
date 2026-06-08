"""Offline tests for the WP-5 live interview state machine.

These import ONLY ``deepinterview_agent.live.state`` (never ``livekit``), so they
pass with the optional ``livekit-agents`` extra absent. A valid
``InterviewContext`` is produced by running the WP-6 prep pipeline with the
deterministic default adapters (MockLLM / MockSearch / MemoryRepository) — no
keys, no network.

The mock ``QuestionPlan`` carries exactly one question (all section ``intro``),
so for the ``next_section`` case we augment the plan with a second question in a
different section. Each test builds its OWN ``InterviewUserdata`` so cursor
mutations never leak between assertions.
"""

from __future__ import annotations

import asyncio

from deepinterview_agent.core.deps import build_deps
from deepinterview_agent.live import state
from deepinterview_agent.live.state import InterviewUserdata
from deepinterview_agent.prep import run_prep
from deepinterview_agent.shared_models import (
    AnswerRecord,
    InterviewContext,
    LanguageMode,
    PrepRequest,
)


def _build_context() -> InterviewContext:
    """Run the offline prep pipeline and load the resulting InterviewContext."""
    deps = build_deps()
    req = PrepRequest(
        cv_url="https://example.com/cv.pdf",
        jd_text="Senior Backend Engineer building distributed payment systems in Python.",
        company="ExampleCorp",
        language_mode=LanguageMode(primary="en", mixed=False),
    )
    session_id = asyncio.run(run_prep(req, deps))
    ctx = asyncio.run(deps.repo.load_context(session_id))
    assert ctx is not None
    return ctx


def _userdata() -> InterviewUserdata:
    ctx = _build_context()
    return InterviewUserdata(ctx=ctx, session_id=ctx.session_id)


def _userdata_two_sections() -> InterviewUserdata:
    """A userdata whose plan has a second question in a different section."""
    ctx = _build_context()
    first = ctx.plan.questions[0]
    # The mock first question is section "intro"; append a "behavioral" one.
    second = first.model_copy(update={"id": "q_behavioral", "section": "behavioral"})
    ctx.plan.questions.append(second)
    return InterviewUserdata(ctx=ctx, session_id=ctx.session_id)


def test_current_question_returns_first_question() -> None:
    ud = _userdata()
    q = state.current_question(ud)
    assert q is not None
    assert q is ud.ctx.plan.questions[0]
    assert ud.ctx.cursor == 0


def test_advance_moves_cursor() -> None:
    ud = _userdata()
    assert ud.ctx.cursor == 0
    state.advance(ud)
    assert ud.ctx.cursor == 1


def test_save_answer_appends_record_with_matching_question_id() -> None:
    ud = _userdata()
    current = state.current_question(ud)
    assert current is not None

    record = state.save_answer(
        ud,
        transcript="I led the migration to a sharded payments ledger.",
        started_at="2026-06-08T09:00:00Z",
        ended_at="2026-06-08T09:01:30Z",
    )

    assert isinstance(record, AnswerRecord)
    assert record.question_id == current.id
    assert ud.ctx.answers[-1] is record
    assert len(ud.ctx.answers) == 1
    assert record.transcript.startswith("I led the migration")


def test_advance_until_complete_then_no_current_question() -> None:
    ud = _userdata()
    assert not state.is_complete(ud)

    # Bounded loop: advance once per planned question.
    steps = 0
    max_steps = len(ud.ctx.plan.questions) + 5
    while not state.is_complete(ud) and steps < max_steps:
        assert state.current_question(ud) is not None
        state.advance(ud)
        steps += 1

    assert state.is_complete(ud)
    assert state.current_question(ud) is None
    assert state.current_section(ud) is None
    assert ud.ctx.cursor == len(ud.ctx.plan.questions)


def test_next_section_jumps_to_a_different_section() -> None:
    ud = _userdata_two_sections()
    starting = state.current_section(ud)
    assert starting is not None  # "intro"

    nxt = state.next_section(ud)
    assert nxt is not None
    assert nxt.section != starting
    # The cursor now points at the first question of the new section.
    assert state.current_question(ud) is nxt
    assert state.current_section(ud) == nxt.section


def test_next_section_at_end_returns_none() -> None:
    ud = _userdata()
    # Drive to the end so there is no later section.
    ud.ctx.cursor = len(ud.ctx.plan.questions)
    assert state.next_section(ud) is None
    assert state.is_complete(ud)


def test_add_turn_and_compact_summary() -> None:
    ud = _userdata()
    state.add_turn(ud, "assistant", "Tell me about a hard bug you fixed.")
    state.add_turn(ud, "user", "I traced a race condition in our ledger writer.")
    assert ud.transcript == [
        {"role": "assistant", "text": "Tell me about a hard bug you fixed."},
        {"role": "user", "text": "I traced a race condition in our ledger writer."},
    ]

    summary = state.compact_summary(ud)
    assert ud.ctx.candidate.name in summary
    assert ud.ctx.job.title in summary
    assert ud.ctx.candidate.summary_120w in summary
