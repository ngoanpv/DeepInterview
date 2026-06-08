"""Adversarial score verification for the WP-7 scoring pipeline (gated, off by default).

After the evaluator produces per-competency scores, this optional second pass
re-examines the *low/borderline* ones (weak/developing bands) with a sceptical
reviewer prompt, catching the cases the first pass over- or under-scored. It is a
pure refinement: the competency list stays one-to-one and order-preserving, every
returned score is clamped to 0-5, and ``level`` is re-derived from the (possibly
adjusted) number via :func:`level_for_score` so the band always agrees.

Safety first: each LLM call is wrapped in :func:`_guarded` (copied from the coach),
so ANY failure — timeout, malformed output, provider error — leaves that score
*unchanged*. Enabled via ``Settings.enable_score_verifier``; deterministic offline
with ``MockLLM`` (every mock verdict is identical), and a no-op when off.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from ..core.logging import get_logger
from ..shared_models import CompetencyScore
from .evaluator import level_for_score
from .prompts import verify_score_prompts

if TYPE_CHECKING:
    from ..core.deps import Deps
    from ..shared_models import InterviewContext

log = get_logger(__name__)

__all__ = ["verify_scores"]

# Only scores in these bands are worth a second, adversarial look; strong/solid
# scores are left untouched.
_VERIFY_LEVELS = frozenset({"weak", "developing"})


class _Verdict(BaseModel):
    """LLM verdict for one adversarial score check; the rest is pinned deterministically."""

    model_config = ConfigDict(extra="forbid")
    justified: bool
    adjusted_score: float
    reason: str


def _clamp_score(value: float) -> float:
    """Clamp a raw score into the documented 0-5 range."""
    return max(0.0, min(5.0, float(value)))


async def _guarded(coro, *, label: str, timeout: float):
    """Await ``coro`` with a timeout; on ANY error return ``None`` (caller falls back)."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except Exception:  # noqa: BLE001 - the verifier must never change scores on failure
        log.exception("verifier: check %r failed; keeping original score", label)
        return None


async def verify_scores(
    ctx: InterviewContext,
    comp_scores: list[CompetencyScore],
    deps: Deps,
) -> list[CompetencyScore]:
    """Adversarially re-check low/borderline scores; return a refined, same-shape list.

    The output is one-to-one and order-preserving with ``comp_scores``. Strong and
    solid scores pass through unchanged; for weak/developing ones the LLM is asked
    whether the score is justified, and if not its clamped ``adjusted_score`` is
    used. Every returned ``level`` is re-derived from the final score. Any guarded
    failure keeps the original score object.
    """
    timeout = deps.settings.score_verifier_timeout_sec
    verified: list[CompetencyScore] = []
    for cs in comp_scores:
        if cs.level not in _VERIFY_LEVELS:
            verified.append(cs)
            continue

        system, user = verify_score_prompts(cs.competency, cs.evidence, cs.score)
        verdict = await _guarded(
            deps.llm.complete_json(system=system, user=user, schema=_Verdict),
            label=f"score:{cs.competency}",
            timeout=timeout,
        )
        if verdict is None or verdict.justified:
            # Failure or "score stands": keep the original untouched.
            verified.append(cs)
            continue

        adjusted = _clamp_score(verdict.adjusted_score)
        verified.append(
            CompetencyScore(
                competency=cs.competency,
                score=adjusted,
                evidence=cs.evidence,
                level=level_for_score(adjusted),
            )
        )
    return verified
