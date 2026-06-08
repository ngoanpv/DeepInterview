"""Prompt builders for the WP-4 Study Coach (kept separate from logic, like post/)."""

from __future__ import annotations


def study_module_prompts(competency: str, evidence: str, level: str) -> tuple[str, str]:
    """Prompt to design ONE study module that closes a weak-competency gap."""
    system = (
        "You are an expert interview-prep coach. Given a competency the candidate "
        "was weak on and the evidence from their interview, design ONE focused, "
        "actionable study module to close the gap. Return JSON with: title (short, "
        "concrete), rationale (one sentence tying it to the observed gap), and "
        "est_min (focused minutes to complete, between 10 and 45)."
    )
    user = (
        f"Competency: {competency}\n"
        f"Observed level: {level}\n"
        f"Evidence from the interview: {evidence or '(no specific evidence captured)'}\n"
    )
    return system, user


def coach_chat_prompts(query: str, grounded_context: str, lang: str) -> tuple[str, str]:
    """Prompt to TEACH an answer to a learner question, grounded where possible."""
    system = (
        "You are a supportive, precise interview-prep coach. Answer the candidate's "
        "question by TEACHING: give a clear, structured explanation with one concrete "
        "example, grounded in the provided context when it is relevant. Reply in the "
        f"candidate's language ({lang}). Return JSON with: answer (the taught "
        "explanation) and follow_ups (1-3 short suggested next questions)."
    )
    user = (
        f"Question: {query}\n\n"
        "Grounded context from the knowledge base "
        f"(use if relevant, ignore if not):\n{grounded_context or '(no grounded notes found)'}\n"
    )
    return system, user
