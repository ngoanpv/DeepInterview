"""Prompt builders for the WP-7 scoring pipeline.

English-first: every system prompt is in English. The post phase is
latency-tolerant, so prompts here can be richer than the live agent's. Each
builder returns a ``(system, user)`` tuple whose ``user`` payload is a compact,
model-readable summary of the relevant interview state (question + rubric +
candidate answer), keeping each call self-contained.

The mock LLM ignores prompt content entirely, so these strings only matter once
a real provider is wired; the deterministic offline behaviour comes from the
post modules overriding the structurally-significant fields themselves (e.g.
``competency`` and ``level`` in the evaluator).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..shared_models import (
        CandidateProfile,
        InterviewContext,
        PlannedQuestion,
        RubricItem,
    )


def _question_en(question: PlannedQuestion) -> str:
    """Best-effort English question text (falls back to any available entry)."""
    text = question.text
    return text.get("en") or next(iter(text.values()), "")


def _rubric_lines(rubric: list[RubricItem]) -> str:
    if not rubric:
        return "- (no rubric provided)"
    return "\n".join(
        f"- {item.criterion} (weight {item.weight:.2f}): {item.description}" for item in rubric
    )


# --- competency evaluation ---------------------------------------------------


def evaluate_answer_prompts(
    question: PlannedQuestion,
    answer_transcript: str | None,
) -> tuple[str, str]:
    """System/user prompts to score one answer against its question rubric.

    ``answer_transcript`` is ``None`` when the candidate never answered the
    question; the prompt asks for a low, evidence-light score in that case.
    """
    system = (
        "You are a rigorous, fair interview assessor. Score the candidate's answer "
        "to a single interview question against the provided rubric on a 0-5 scale "
        "(0 = no relevant content, 3 = solid, 5 = exceptional). Weigh each rubric "
        "criterion by its weight. Cite concrete evidence from the answer in the "
        "evidence field. If no answer was given, assign a low score and say the "
        "question was not answered. Respond ONLY with the requested schema."
    )
    answer_block = (
        answer_transcript.strip()
        if answer_transcript and answer_transcript.strip()
        else "(the candidate did not answer this question)"
    )
    user = (
        f"TARGET COMPETENCY: {question.target_competency}\n"
        f"SECTION: {question.section}; DIFFICULTY: {question.difficulty}\n\n"
        f"QUESTION:\n{_question_en(question)}\n\n"
        f"RUBRIC:\n{_rubric_lines(question.rubric)}\n\n"
        f"CANDIDATE ANSWER:\n{answer_block}"
    )
    return system, user


# --- adversarial score verification ------------------------------------------


def verify_score_prompts(
    competency: str,
    evidence: str,
    score: float,
) -> tuple[str, str]:
    """System/user prompts for a second, adversarial pass over a low/borderline score.

    Asks a sceptical reviewer whether the original 0-5 ``score`` for ``competency``
    is justified by ``evidence``; if not, it proposes an ``adjusted_score`` (also
    0-5) and a short ``reason``. The post module clamps the result and re-derives
    the band, so only the numbers and the boolean verdict are trusted here.
    """
    system = (
        "You are a sceptical second reviewer auditing an interview score for "
        "over- or under-scoring. Given one competency, the evidence cited, and the "
        "original 0-5 score, decide whether that score is JUSTIFIED by the evidence. "
        "If it is, set justified=true and repeat the original score as adjusted_score. "
        "If it is not, set justified=false and give a corrected adjusted_score on the "
        "same 0-5 scale (0 = no relevant content, 3 = solid, 5 = exceptional) with a "
        "brief reason. Be conservative; only move the score when the evidence clearly "
        "warrants it. Respond ONLY with the requested schema."
    )
    user = (
        f"COMPETENCY: {competency}\n"
        f"ORIGINAL SCORE: {score:.2f} / 5\n\n"
        f"EVIDENCE CITED:\n{evidence or '(no evidence was recorded)'}"
    )
    return system, user


# --- language coaching -------------------------------------------------------


def language_coach_prompts(transcript: str, primary_language: str) -> tuple[str, str]:
    """System/user prompts to assess spoken-language quality across the interview."""
    system = (
        "You are a supportive spoken-English (and multilingual) communication coach. "
        "Across the full interview transcript, assess the candidate's spoken delivery: "
        "fluency_score and clarity_score on a 0-5 scale, an approximate filler_word_count "
        "(um, uh, like, you know), notes on any code-switching between languages, and "
        "pronunciation notes. Be encouraging and specific. Respond ONLY with the "
        "requested schema."
    )
    user = (
        f"PRIMARY LANGUAGE: {primary_language}\n\n"
        f"FULL INTERVIEW TRANSCRIPT (candidate turns):\n{transcript or '(no transcript captured)'}"
    )
    return system, user


# --- model answers -----------------------------------------------------------


def model_answer_prompts(
    question: PlannedQuestion,
    candidate: CandidateProfile,
    answer_transcript: str | None,
) -> tuple[str, str]:
    """System/user prompts to draft an exemplary answer to one question."""
    system = (
        "You are an expert interview coach. Write a concise, strong model answer to "
        "the interview question below, tailored to this candidate's background so they "
        "can study and reuse it. Use a clear structure (e.g. STAR for behavioral). "
        "Keep it under ~180 words. Respond with the model answer text only."
    )
    given = (
        f"\n\nCANDIDATE'S ACTUAL ANSWER (improve on this):\n{answer_transcript.strip()}"
        if answer_transcript and answer_transcript.strip()
        else ""
    )
    user = (
        f"CANDIDATE: {candidate.headline} ({candidate.years_experience}y, "
        f"{candidate.seniority})\n"
        f"SKILLS: {', '.join(candidate.skills)}\n\n"
        f"QUESTION ({question.target_competency}):\n{_question_en(question)}"
        f"{given}"
    )
    return system, user


# --- report synthesis --------------------------------------------------------


def report_summary_prompts(
    ctx: InterviewContext,
    competency_lines: str,
    overall_score: float,
) -> tuple[str, str]:
    """System/user prompts to synthesize the narrative parts of the scorecard.

    Produces the free-text strengths / weaknesses / next_steps / summary; the
    structured numeric fields are assembled deterministically by ``report``.
    """
    system = (
        "You are an interview coach writing the candidate's feedback report. Given the "
        "per-competency scores and the role, produce: a list of concrete strengths, a "
        "list of weaknesses, prioritized next_steps the candidate should study, and a "
        "warm, honest summary paragraph. Tie everything to evidence from the scores. "
        "Respond ONLY with the requested schema."
    )
    user = (
        f"ROLE: {ctx.job.title} ({ctx.job.seniority}) at {ctx.job.company_name}\n"
        f"CANDIDATE: {ctx.candidate.headline}\n"
        f"OVERALL SCORE: {overall_score:.2f} / 5\n\n"
        f"PER-COMPETENCY SCORES:\n{competency_lines}"
    )
    return system, user
