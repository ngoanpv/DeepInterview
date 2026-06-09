"""Deterministic input-quality heuristics for prep inputs.

The prep pipeline is expensive (LLM + search calls), so before running it we
cheaply reject (or warn about) obviously meaningless inputs — empty strings,
random keyboard mashing ("asdasdasd"), repeated characters ("aaaaaaaa"), or
symbol/whitespace soup. These checks are purely deterministic (no LLM), so they
run offline and never cost a model call.

Two entry points:

* :func:`assess_text` — judge a single field; returns ``(is_meaningful, reason)``.
* :func:`validate_prep_inputs` — judge a whole :class:`PrepRequest`; returns
  ``(ok, warnings)``. ``ok`` is ``False`` (→ session ``rejected``) only when BOTH
  the CV and the JD are meaningless; an individual junk field (or a junk company)
  yields a human-readable warning but keeps prep running.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from ..shared_models import PrepRequest

__all__ = ["assess_text", "validate_prep_inputs"]

# Minimum meaningful lengths (after stripping) per input kind.
_MIN_LEN_CV = 30
_MIN_LEN_JD = 30
_MIN_LEN_COMPANY = 2

# Fraction of characters that must be ASCII letters for text to look word-like.
_MIN_ALPHA_RATIO = 0.45

# A short repeated pattern covering more than this fraction of content is junk.
_REPETITION_THRESHOLD = 0.70

_VOWELS = set("aeiouyAEIOUY")
# A run of >= 3 consecutive ASCII letters signals at least one real-ish token.
_WORD_RUN_RE = re.compile(r"[A-Za-z]{3,}")
_TOKEN_RE = re.compile(r"[A-Za-z]+")

_KIND_LABEL = {"cv": "CV", "jd": "job description", "company": "company name"}


def _friendly(kind: str, reason: str) -> str:
    label = _KIND_LABEL.get(kind, kind)
    return f"The {label} {reason}"


def _looks_like_url(text: str) -> bool:
    """True if ``text`` is a document pointer we shouldn't word-check.

    Accepts a single http(s) URL token *and* a ``data:`` URL (base64 file bytes
    from the no-storage upload path). Both are pointers to a real document whose
    text is extracted before analysis, so they must not be flagged as junk.
    """
    stripped = text.strip()
    # A data: URL carries no whitespace meaning; check the scheme prefix directly
    # (urlparse treats the whole payload as the path, which is fine here).
    if stripped.startswith("data:"):
        return True
    if " " in stripped or "\n" in stripped:
        return False
    parsed = urlparse(stripped)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _dominant_pattern_ratio(text: str) -> float:
    """Largest fraction of ``text`` covered by repeating a 1- or 2-char pattern.

    Catches ``"aaaaaa"`` (1-char) and ``"asasasas"`` / ``"asdasdasd"`` style
    low-entropy mashing. Returns a value in ``[0, 1]``.
    """
    compact = re.sub(r"\s+", "", text)
    n = len(compact)
    if n == 0:
        return 1.0

    # 1-char domination: the single most common character.
    most_common_char = Counter(compact).most_common(1)[0][1]
    best = most_common_char / n

    # A period of length k only counts as *repetition* when the string is at
    # least two full periods long (n >= 2k) — otherwise a short token trivially
    # equals its own single tiling (e.g. "IBM" is not repetition).

    # 2-char period domination: how much of the string equals a 2-char tiling.
    if n >= 4:
        for offset in (0, 1):
            unit = compact[offset : offset + 2]
            if len(unit) < 2:
                continue
            tiled = (unit * (n // 2 + 1))[: n - offset]
            matches = sum(1 for a, b in zip(compact[offset:], tiled) if a == b)
            best = max(best, matches / n)

    # 3-char period domination (e.g. "asdasdasd").
    if n >= 6:
        unit = compact[:3]
        tiled = (unit * (n // 3 + 1))[:n]
        matches = sum(1 for a, b in zip(compact, tiled) if a == b)
        best = max(best, matches / n)

    return best


def assess_text(text: str, *, kind: str, min_len: int) -> tuple[bool, str | None]:
    """Judge whether ``text`` looks like real, meaningful content.

    Returns ``(is_meaningful, reason_if_not)``. ``reason`` is a friendly,
    user-facing sentence when the text is rejected, else ``None``.
    """
    if text is None:
        return False, _friendly(kind, "looks empty — please paste the real content.")

    stripped = text.strip()

    # Near-empty after stripping whitespace.
    if not stripped:
        return False, _friendly(kind, "looks empty — please paste the real content.")

    # A bare URL (common for cv_url) is acceptable as a pointer to a real document.
    if kind == "cv" and _looks_like_url(text):
        return True, None

    # Too short to carry any signal.
    if len(stripped) < min_len:
        return False, _friendly(
            kind, "is too short to be meaningful — please paste the full content."
        )

    # Near-empty once symbols/whitespace are removed (symbol soup). Unicode-aware
    # so non-Latin scripts (CJK, Devanagari, …) count as real content.
    alnum = [c for c in stripped if c.isalnum()]
    if not alnum:
        return False, _friendly(
            kind, "looks empty or like random symbols — please paste the real content."
        )

    # Low alphabetic ratio: mostly digits/symbols, not prose. ``str.isalpha`` is
    # Unicode-aware, so CJK/Devanagari/Cyrillic letters all count.
    letters = [c for c in stripped if c.isalpha()]
    if len(letters) / len(stripped) < _MIN_ALPHA_RATIO:
        return False, _friendly(
            kind,
            "looks empty or like random characters — please paste the real content.",
        )

    # The "word-like token" and "vowel" heuristics are Latin-specific (they assume
    # alphabetic words with vowels). Apply them only to ASCII-dominant text;
    # non-Latin scripts have already cleared the length + alpha-ratio gates, which
    # is enough signal that they are real content rather than keyboard mashing.
    ascii_letters = sum(1 for c in letters if c.isascii())
    if ascii_letters / len(letters) >= 0.5:
        # No word-like token: no run of >= 3 ASCII letters at all.
        if not _WORD_RUN_RE.search(stripped):
            return False, _friendly(
                kind,
                "looks empty or like random characters — please paste the real content.",
            )

        # No token contains a vowel (e.g. "asdfgh hjkl") -> keyboard mashing.
        tokens = _TOKEN_RE.findall(stripped)
        if tokens and not any(any(ch in _VOWELS for ch in tok) for tok in tokens):
            return False, _friendly(
                kind,
                "looks like random characters — please paste the real content.",
            )

    # Repetition: one short pattern dominates the content.
    if _dominant_pattern_ratio(stripped) > _REPETITION_THRESHOLD:
        return False, _friendly(
            kind,
            "looks like repeated or random characters — please paste the real content.",
        )

    return True, None


def validate_prep_inputs(
    req: PrepRequest, *, cv_text: str | None = None
) -> tuple[bool, list[str]]:
    """Assess the CV, JD and company of a ``PrepRequest``.

    ``cv_text`` is the fetched CV document text when available (preferred); when
    omitted the raw ``req.cv_url`` string is assessed instead.

    Returns ``(ok, warnings)``. ``ok`` is ``False`` only when BOTH the CV and the
    JD are meaningless (→ the session is rejected); otherwise ``ok`` is ``True``
    and ``warnings`` lists any individual junk field (including a junk company,
    which also signals the caller to skip company research).
    """
    warnings: list[str] = []

    cv_input = cv_text if cv_text is not None else req.cv_url
    cv_ok, cv_reason = assess_text(cv_input, kind="cv", min_len=_MIN_LEN_CV)
    jd_ok, jd_reason = assess_text(req.jd_text, kind="jd", min_len=_MIN_LEN_JD)
    company_ok, company_reason = assess_text(
        req.company, kind="company", min_len=_MIN_LEN_COMPANY
    )

    # Both core inputs junk -> wholly meaningless: reject with both reasons.
    if not cv_ok and not jd_ok:
        reasons = [r for r in (cv_reason, jd_reason) if r]
        return False, reasons

    if not cv_ok and cv_reason:
        warnings.append(cv_reason)
    if not jd_ok and jd_reason:
        warnings.append(jd_reason)
    if not company_ok and company_reason:
        warnings.append(company_reason)

    return True, warnings
