"""Spoken-language assessment for the WP-7 scoring pipeline.

Builds a single :class:`LanguageReport` from the candidate's answer transcripts:
fluency, clarity, an approximate filler-word count, and code-switching /
pronunciation notes. The numeric bounds (0-5 scores, non-negative count) are
clamped here so the report is well-formed regardless of the provider.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..shared_models import LanguageReport
from .prompts import language_coach_prompts

if TYPE_CHECKING:
    from ..core.deps import Deps
    from ..shared_models import InterviewContext


def _transcript(ctx: InterviewContext) -> str:
    """Concatenate the candidate's answer transcripts into one block."""
    parts = [a.transcript.strip() for a in ctx.answers if a.transcript and a.transcript.strip()]
    return "\n\n".join(parts)


def _clamp_score(value: float) -> float:
    return max(0.0, min(5.0, float(value)))


async def coach(ctx: InterviewContext, deps: Deps) -> LanguageReport:
    """Produce the spoken-language report for the interview."""
    transcript = _transcript(ctx)
    primary = ctx.plan.language_mode.primary
    system, user = language_coach_prompts(transcript, primary)
    report = await deps.llm.complete_json(system=system, user=user, schema=LanguageReport)

    # Normalize the numeric fields into their documented ranges.
    return report.model_copy(
        update={
            "fluency_score": _clamp_score(report.fluency_score),
            "clarity_score": _clamp_score(report.clarity_score),
            "filler_word_count": max(0, int(report.filler_word_count)),
        }
    )
