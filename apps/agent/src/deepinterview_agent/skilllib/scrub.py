"""PII scrubbing for skill bodies (WP-10 quality gate).

A skill is de-identified, generalized knowledge — it must never carry a real
candidate's name, email, or phone number. :func:`scrub_pii` is the single choke
point: the distiller runs it before writing a draft, and ``promote`` runs it
again as a safety net before a draft enters the live library.

The substitutions are deliberately conservative regexes plus exact replacement
of any caller-provided names. ``[candidate]`` replaces a name, ``[email]`` /
``[phone]`` replace contact details — so the surrounding prose stays readable.
"""

from __future__ import annotations

import re

# user@host.tld — kept simple; matches the common shapes without over-reaching.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Phone numbers: optional +, then 7+ digits possibly separated by space/-/./()
# Requires at least 7 digits total so it doesn't eat short numbers / years.
_PHONE_RE = re.compile(
    r"(?<![\w.])"  # not mid-word / not a decimal
    r"\+?\d[\d\s().-]{5,}\d"  # leading digit, separators, trailing digit
    r"(?![\w.])"
)


def _digit_count(s: str) -> int:
    return sum(c.isdigit() for c in s)


def _scrub_phones(text: str) -> str:
    def _repl(m: re.Match[str]) -> str:
        return "[phone]" if _digit_count(m.group(0)) >= 7 else m.group(0)

    return _PHONE_RE.sub(_repl, text)


def scrub_pii(text: str, *, names: list[str]) -> str:
    """Return ``text`` with candidate names, emails, and phone numbers removed.

    ``names`` are replaced (case-insensitive, whole-word) with ``[candidate]``;
    emails with ``[email]``; phone-shaped digit runs (>= 7 digits) with
    ``[phone]``. Idempotent: re-running on already-scrubbed text is a no-op.
    """
    out = text

    # Replace provided names first (before regexes), longest first so a full name
    # is caught before its parts and we don't leave a dangling first/last token.
    for name in sorted({n.strip() for n in names if n and n.strip()}, key=len, reverse=True):
        pattern = re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)
        out = pattern.sub("[candidate]", out)

    out = _EMAIL_RE.sub("[email]", out)
    out = _scrub_phones(out)
    return out
