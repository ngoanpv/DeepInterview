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
    q1 = state.current_question(ud)
    assert q1 is not None
    state.add_turn(ud, "assistant", "Tell me about a hard bug you fixed.")
    state.add_turn(ud, "user", "I traced a race condition in our ledger writer.")
    assert ud.transcript == [
        {
            "role": "assistant",
            "text": "Tell me about a hard bug you fixed.",
            "question_id": q1.id,
        },
        {
            "role": "user",
            "text": "I traced a race condition in our ledger writer.",
            "question_id": q1.id,
        },
    ]

    summary = state.compact_summary(ud)
    assert ud.ctx.candidate.name in summary
    assert ud.ctx.job.title in summary
    assert ud.ctx.candidate.summary_120w in summary


def test_add_turn_past_end_has_empty_question_id() -> None:
    ud = _userdata()
    ud.ctx.cursor = len(ud.ctx.plan.questions)
    state.add_turn(ud, "user", "Thanks, goodbye!")
    assert ud.transcript[-1]["question_id"] == ""


def test_reconstruct_answers_recovers_unsaved_user_turns() -> None:
    """A hang-up before save_answer must not drop what the candidate said."""
    ud = _userdata_two_sections()
    q1 = state.current_question(ud)
    assert q1 is not None
    state.add_turn(ud, "assistant", "Tell me about a hard bug you fixed.")
    state.add_turn(ud, "user", "I traced a race condition in our ledger writer")
    state.add_turn(ud, "user", "by bisecting the commit history and adding a regression test.")
    assert ud.ctx.answers == []

    added = state.reconstruct_answers(ud)

    assert added == 1
    record = ud.ctx.answers[-1]
    assert record.question_id == q1.id
    assert record.transcript == (
        "I traced a race condition in our ledger writer "
        "by bisecting the commit history and adding a regression test."
    )


def test_reconstruct_answers_skips_saved_questions_and_is_idempotent() -> None:
    ud = _userdata_two_sections()
    state.add_turn(
        ud, "user", "raw stt text for question one with enough words to clear the substance gate"
    )
    state.save_answer(
        ud,
        transcript="The model's curated answer for question one.",
        started_at="",
        ended_at="",
    )
    state.advance(ud)  # -> q_behavioral
    state.add_turn(
        ud, "user", "an answer the model never saved about leading the on-call rotation overhaul"
    )

    added = state.reconstruct_answers(ud)

    # Only the unsaved second question is recovered; the saved one is untouched.
    assert added == 1
    assert len(ud.ctx.answers) == 2
    assert ud.ctx.answers[0].transcript.startswith("The model's curated")
    assert ud.ctx.answers[1].question_id == "q_behavioral"
    assert ud.ctx.answers[1].transcript == (
        "an answer the model never saved about leading the on-call rotation overhaul"
    )

    # Running again adds nothing.
    assert state.reconstruct_answers(ud) == 0
    assert len(ud.ctx.answers) == 2


def test_reconstruct_answers_ignores_blank_and_assistant_turns() -> None:
    ud = _userdata()
    state.add_turn(ud, "assistant", "Tell me about a hard bug you fixed.")
    state.add_turn(ud, "user", "   ")
    assert state.reconstruct_answers(ud) == 0
    assert ud.ctx.answers == []


# --- recovery edge cases (regression pins for the no_answers production bug) --


def test_reconstruct_answers_turns_follow_cursor_across_advances() -> None:
    """Turns are bucketed by the question active when spoken, not replayed flat.

    Speech before ``advance`` belongs to Q1; speech after belongs to Q2. Recovery
    must yield one record per question, each containing ONLY its own turns.
    """
    ud = _userdata_two_sections()
    q1 = state.current_question(ud)
    assert q1 is not None
    state.add_turn(ud, "user", "first part of answer one about sharding the ledger")
    state.add_turn(ud, "user", "second part of answer one covering the rollout and metrics")

    state.advance(ud)  # get_next_question semantics: cursor -> q_behavioral
    q2 = state.current_question(ud)
    assert q2 is not None
    assert q2.id != q1.id
    state.add_turn(
        ud, "user", "the whole of answer two describing how I mentored two junior engineers"
    )

    added = state.reconstruct_answers(ud)

    assert added == 2
    by_id = {a.question_id: a for a in ud.ctx.answers}
    assert set(by_id) == {q1.id, q2.id}
    # Each record joins only its own turns, in spoken order — no cross-bleed.
    assert by_id[q1.id].transcript == (
        "first part of answer one about sharding the ledger "
        "second part of answer one covering the rollout and metrics"
    )
    assert by_id[q2.id].transcript == (
        "the whole of answer two describing how I mentored two junior engineers"
    )


def test_reconstruct_answers_joins_multi_fragment_answer_in_spoken_order() -> None:
    """Three STT fragments for one question join with single spaces, in order."""
    ud = _userdata()
    q1 = state.current_question(ud)
    assert q1 is not None
    # Fragments carry stray whitespace the way streaming STT finals often do.
    state.add_turn(ud, "user", "  I shipped the ledger")
    state.add_turn(ud, "user", "then I profiled it  ")
    state.add_turn(ud, "user", "and fixed the hot path")

    assert state.reconstruct_answers(ud) == 1
    record = ud.ctx.answers[-1]
    assert record.question_id == q1.id
    assert record.transcript == "I shipped the ledger then I profiled it and fixed the hot path"


def test_reconstruct_answers_preserves_existing_answer_order_for_last_wins() -> None:
    """Recovered records append AFTER saved ones, so ``{a.question_id: a}``
    last-wins indexing (evaluator/report/verifier) can never replace a curated
    answer with a verbatim STT one for the same question id.
    """
    ud = _userdata_two_sections()
    q1 = state.current_question(ud)
    assert q1 is not None
    # Q1: raw speech AND a curated save_answer from the model. The speech
    # clears the substance gate, so ONLY the qid-in-saved guard prevents a
    # second record for Q1.
    state.add_turn(
        ud, "user", "raw stt text the model rewrote about debugging the sharded ledger consistency bug"
    )
    state.save_answer(
        ud,
        transcript="The model's curated answer for question one.",
        started_at="2026-06-08T09:00:00Z",
        ended_at="2026-06-08T09:01:30Z",
    )
    state.advance(ud)  # -> q_behavioral
    state.add_turn(
        ud, "user", "speech for question two that was never saved about migrating the billing service"
    )

    added = state.reconstruct_answers(ud)

    # qid-in-saved guard, asserted directly: speech for an already-saved Q never
    # creates a second record for that id.
    assert added == 1
    q1_records = [a for a in ud.ctx.answers if a.question_id == q1.id]
    assert len(q1_records) == 1
    assert q1_records[0].transcript == "The model's curated answer for question one."

    # Ordering: every recovered record sits after every saved record, so the
    # last-wins index resolves each id to the curated answer when one exists.
    assert [a.question_id for a in ud.ctx.answers] == [q1.id, "q_behavioral"]
    by_id = {a.question_id: a for a in ud.ctx.answers}
    assert by_id[q1.id].transcript.startswith("The model's curated")
    assert by_id["q_behavioral"].transcript == (
        "speech for question two that was never saved about migrating the billing service"
    )


def test_evaluate_difficulty_sees_recovered_answers() -> None:
    """Recovery feeds adaptive difficulty: a recovered answer counts in
    ``answered_in_section`` exactly like a tool-saved one. (A recovered answer
    always carries at least ``_MIN_RECOVERED_WORDS`` words — the substance gate
    — so it can never read as "thin" / flip the heuristic to "easier".)
    """
    ud = _userdata()
    section = state.current_section(ud)
    assert section is not None and section != "wrap"

    # Before recovery there is no evidence in the section.
    before = state.evaluate_difficulty(ud)
    assert before.answered_in_section == 0
    assert before.recommendation == "advance"

    # A moderate (>= _MIN_RECOVERED_WORDS, <= _RICH_WORDS) unsaved answer.
    state.add_turn(
        ud, "user", "I used Python with asyncio to rebuild the ingestion worker around batching."
    )
    assert state.reconstruct_answers(ud) == 1

    after = state.evaluate_difficulty(ud)
    assert after.answered_in_section == 1
    # Moderate substance in a covered section -> stay on plan.
    assert after.recommendation == "advance"


def test_reconstruct_answers_substance_gate_drops_small_talk() -> None:
    """Sub-threshold speech is small talk, not an answer (confirmed-review pin).

    The greeting reply ("Hi, nice to meet you!") is tagged with Q1's id because
    ``on_enter`` greets and asks Q1 in one breath. Recovering it would fire the
    full LLM scoring pipeline on junk and replace the honest ``no_answers``
    empty state with a misleading near-zero report.
    """
    ud = _userdata()
    state.add_turn(ud, "assistant", "Hi! I'll be running your mock interview today.")
    state.add_turn(ud, "user", "Hi, nice to meet you, I'm ready!")

    assert state.reconstruct_answers(ud) == 0
    assert ud.ctx.answers == []


def test_reconstruct_answers_substance_gate_boundary() -> None:
    """The gate is exact: 11 joined words drop, 12 recover — and fragments
    accumulate toward the threshold across turns for the same question.
    """
    eleven = "one two three four five six seven eight nine ten eleven"
    ud = _userdata()
    state.add_turn(ud, "user", eleven)
    assert state.reconstruct_answers(ud) == 0
    assert ud.ctx.answers == []

    # A later fragment for the same question pushes it over the threshold.
    state.add_turn(ud, "user", "twelve")
    assert state.reconstruct_answers(ud) == 1
    assert ud.ctx.answers[-1].transcript == f"{eleven} twelve"


def test_trailing_empty_save_answer_does_not_block_recovery() -> None:
    """The saved-guard mirrors the scorers' last-wins indexing: a trailing
    ``save_answer("")`` voids the question for scoring, so real speech for it
    must still be recovered — and the recovered record, appended last, is what
    ``{a.question_id: a}`` resolves to.
    """
    ud = _userdata()
    q1 = state.current_question(ud)
    assert q1 is not None
    state.add_turn(
        ud, "user", "I rebuilt the payments retry queue and cut duplicate charges to zero."
    )
    state.save_answer(ud, transcript="A curated answer.", started_at="", ended_at="")
    # The model fumbles a second tool call: the trailing record voids Q1 under
    # last-wins indexing.
    state.save_answer(ud, transcript="", started_at="", ended_at="")

    assert state.reconstruct_answers(ud) == 1
    by_id = {a.question_id: a for a in ud.ctx.answers}
    assert by_id[q1.id].transcript.startswith("I rebuilt the payments retry queue")


def test_reconstruct_answers_never_recovers_wrap_phase_speech() -> None:
    """User speech after the last planned question (question_id == "") is
    goodbye chatter, not an answer — it must never become an AnswerRecord.
    """
    ud = _userdata()
    ud.ctx.cursor = len(ud.ctx.plan.questions)  # past the end
    state.add_turn(ud, "user", "Thanks, this was a great conversation, goodbye!")
    assert ud.transcript[-1]["question_id"] == ""

    assert state.reconstruct_answers(ud) == 0
    assert ud.ctx.answers == []
