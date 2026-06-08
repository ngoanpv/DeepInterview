"""Offline tests for the pure adaptive-difficulty logic in ``live.state``.

These import ONLY ``deepinterview_agent.live.state`` (never ``livekit``), so they
pass with the optional ``livekit-agents`` extra absent. The decision logic is a
pure function of the plan questions + cursor + answer log, so we drive it with
lightweight ``SimpleNamespace`` fakes instead of building a full
``InterviewContext`` (which would require many nested required models). The logic
is deterministic — no clock, no randomness — so every assertion is reproducible.

The shape the pure functions read is intentionally minimal:

    ud.ctx.cursor                      -> int
    ud.ctx.plan.questions[i].id        -> str
    ud.ctx.plan.questions[i].section   -> str
    ud.ctx.plan.questions[i].difficulty-> int
    ud.ctx.answers[j].question_id      -> str
    ud.ctx.answers[j].transcript       -> str

so a ``SimpleNamespace`` graph that exposes exactly those is a faithful stand-in.
"""

from __future__ import annotations

from types import SimpleNamespace

from deepinterview_agent.live import state


def _q(qid: str, section: str, difficulty: int = 3) -> SimpleNamespace:
    return SimpleNamespace(id=qid, section=section, difficulty=difficulty)


def _a(question_id: str, transcript: str) -> SimpleNamespace:
    return SimpleNamespace(question_id=question_id, transcript=transcript)


def _ud(questions, answers, cursor) -> SimpleNamespace:
    """A livekit-free InterviewUserdata stand-in exposing the read shape."""
    plan = SimpleNamespace(questions=list(questions))
    ctx = SimpleNamespace(plan=plan, answers=list(answers), cursor=cursor)
    return SimpleNamespace(ctx=ctx, session_id="s_test", transcript=[])


def _words(n: int) -> str:
    return " ".join("word" for _ in range(n))


def test_thin_answers_recommend_easier() -> None:
    # One technical question answered with a very short (thin) answer -> easier.
    questions = [_q("q1", "technical", difficulty=3)]
    answers = [_a("q1", _words(3))]
    sig = state.evaluate_difficulty(_ud(questions, answers, cursor=0))
    assert sig.recommendation == "easier"
    assert sig.section == "technical"
    assert isinstance(sig.rationale, str) and sig.rationale


def test_rich_answers_recommend_harder() -> None:
    # A long, substantive answer on a non-maxed-difficulty question -> harder.
    questions = [_q("q1", "technical", difficulty=2)]
    answers = [_a("q1", _words(120))]
    sig = state.evaluate_difficulty(_ud(questions, answers, cursor=0))
    assert sig.recommendation == "harder"


def test_rich_answers_at_max_difficulty_advance_not_harder() -> None:
    # Strong answer but the question is already at the top of the 1-5 band:
    # there's no harder rung in this section, so advance instead of harder.
    questions = [_q("q1", "technical", difficulty=5)]
    answers = [_a("q1", _words(120))]
    sig = state.evaluate_difficulty(_ud(questions, answers, cursor=0))
    assert sig.recommendation == "advance"


def test_section_fully_answered_recommends_advance() -> None:
    # Both questions in the section answered solidly (mid-length) -> advance.
    questions = [
        _q("q1", "technical", difficulty=3),
        _q("q2", "technical", difficulty=3),
        _q("q3", "coding", difficulty=3),
    ]
    answers = [_a("q1", _words(40)), _a("q2", _words(40))]
    # Cursor sits on q2 (last unanswered-or-current of the technical section);
    # the whole section is answered, so move on.
    sig = state.evaluate_difficulty(_ud(questions, answers, cursor=1))
    assert sig.recommendation == "advance"
    assert sig.section == "technical"


def test_no_answers_yet_is_neutral_advance() -> None:
    # Nothing answered in the current section yet -> no signal to go harder or
    # easier; the default keeps the interview moving on plan (advance).
    questions = [_q("q1", "technical", difficulty=3)]
    sig = state.evaluate_difficulty(_ud(questions, [], cursor=0))
    assert sig.recommendation == "advance"
    assert sig.answered_in_section == 0


def test_past_end_recommends_wrap() -> None:
    questions = [_q("q1", "technical", difficulty=3)]
    answers = [_a("q1", _words(40))]
    sig = state.evaluate_difficulty(_ud(questions, answers, cursor=5))
    assert sig.recommendation == "wrap"
    assert sig.section is None


def test_wrap_section_recommends_wrap() -> None:
    # The current section is the terminal 'wrap' section -> wrap regardless.
    questions = [_q("q1", "wrap", difficulty=1)]
    answers = [_a("q1", _words(40))]
    sig = state.evaluate_difficulty(_ud(questions, answers, cursor=0))
    assert sig.recommendation == "wrap"


def test_is_deterministic_across_repeated_calls() -> None:
    questions = [_q("q1", "technical", difficulty=2)]
    answers = [_a("q1", _words(120))]
    ud = _ud(questions, answers, cursor=0)
    first = state.evaluate_difficulty(ud)
    second = state.evaluate_difficulty(ud)
    assert first == second
    # Pure: the cursor must be untouched by the decision logic.
    assert ud.ctx.cursor == 0


def test_rationale_string_helper_matches_signal() -> None:
    questions = [_q("q1", "technical", difficulty=3)]
    answers = [_a("q1", _words(3))]
    ud = _ud(questions, answers, cursor=0)
    sig = state.evaluate_difficulty(ud)
    text = state.difficulty_hint(ud)
    assert sig.recommendation in text
    assert sig.rationale in text
