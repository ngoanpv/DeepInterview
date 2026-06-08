"""Offline tests for the deterministic input-quality heuristics."""

from __future__ import annotations

from deepinterview_agent.core.validation import assess_text, validate_prep_inputs
from deepinterview_agent.shared_models import LanguageMode, PrepRequest

_REAL_JD = (
    "We are hiring a Senior Backend Engineer to design and operate distributed "
    "payment systems in Python. You will own service reliability and mentor peers."
)
_REAL_CV = (
    "Jane Doe — Backend Engineer with 8 years building Python microservices, "
    "Postgres, and event-driven systems at fintech scale."
)


def test_assess_text_accepts_real_jd() -> None:
    ok, reason = assess_text(_REAL_JD, kind="jd", min_len=30)
    assert ok is True
    assert reason is None


def test_assess_text_accepts_real_cv() -> None:
    ok, reason = assess_text(_REAL_CV, kind="cv", min_len=30)
    assert ok is True
    assert reason is None


def test_assess_text_accepts_bare_cv_url() -> None:
    ok, reason = assess_text("https://example.com/cv.pdf", kind="cv", min_len=30)
    assert ok is True
    assert reason is None


def test_assess_text_accepts_non_latin_scripts() -> None:
    # Real CJK / Devanagari content must NOT be flagged as gibberish
    # (golden rule #3: English-first, multilingual — zh/ja/hi are supported).
    japanese = (
        "当社はPythonでバックエンドエンジニアを募集しています。"
        "分散決済システムの設計と運用を担当していただきます。"
    )
    ok, reason = assess_text(japanese, kind="jd", min_len=30)
    assert ok is True, reason

    chinese = "我们正在招聘一名资深后端工程师，负责设计和运营分布式支付系统，使用Python语言。"
    ok, reason = assess_text(chinese, kind="cv", min_len=30)
    assert ok is True, reason

    hindi = (
        "हम पायथन में वितरित भुगतान प्रणाली बनाने के लिए एक वरिष्ठ "
        "बैकएंड इंजीनियर की तलाश कर रहे हैं।"
    )
    ok, reason = assess_text(hindi, kind="jd", min_len=30)
    assert ok is True, reason


def test_assess_text_rejects_empty() -> None:
    ok, reason = assess_text("   \n\t  ", kind="jd", min_len=30)
    assert ok is False
    assert reason and "job description" in reason


def test_assess_text_rejects_too_short() -> None:
    ok, reason = assess_text("hire eng", kind="jd", min_len=30)
    assert ok is False
    assert reason


def test_assess_text_rejects_repeated_chars() -> None:
    ok, reason = assess_text("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", kind="jd", min_len=30)
    assert ok is False
    assert reason


def test_assess_text_rejects_keyboard_mashing() -> None:
    ok, reason = assess_text("asdasdasdasdasdasdasdasdasdasdasd", kind="cv", min_len=30)
    assert ok is False
    assert reason


def test_assess_text_rejects_symbol_soup() -> None:
    ok, reason = assess_text("!@#$%^&*()!@#$%^&*()!@#$%^&*()!@#$", kind="jd", min_len=30)
    assert ok is False
    assert reason


def test_assess_text_rejects_no_vowel_tokens() -> None:
    # Long enough, alpha-heavy, but no token contains a vowel -> keyboard mashing.
    ok, reason = assess_text("xkcd zxcv bcdf ghjk lmnp qrst vwxz", kind="cv", min_len=30)
    assert ok is False
    assert reason


def test_assess_company_short_threshold() -> None:
    # A real (short) company name passes the tiny company threshold.
    ok, _ = assess_text("IBM", kind="company", min_len=2)
    assert ok is True
    # A single empty/garbage character fails.
    bad, reason = assess_text("$", kind="company", min_len=2)
    assert bad is False
    assert reason and "company" in reason


def _req(cv: str, jd: str, company: str) -> PrepRequest:
    return PrepRequest(
        cv_url=cv,
        jd_text=jd,
        company=company,
        language_mode=LanguageMode(primary="en", mixed=False),
    )


def test_validate_both_junk_rejects() -> None:
    ok, warnings = validate_prep_inputs(
        _req("aaaaaaaaaaaaaaaaaaaa", "!!!!!!!!!!!!!!!!!!!!", "Acme"),
        cv_text="aaaaaaaaaaaaaaaaaaaa",
    )
    assert ok is False
    assert warnings, "rejection should carry reasons for both fields"


def test_validate_one_junk_warns_only() -> None:
    # CV is junk but JD is real -> not a rejection, just a warning.
    ok, warnings = validate_prep_inputs(
        _req("aaaaaaaaaaaaaaaaaaaa", _REAL_JD, "Acme"),
        cv_text="aaaaaaaaaaaaaaaaaaaa",
    )
    assert ok is True
    assert any("CV" in w for w in warnings)


def test_validate_junk_company_warns_and_flags() -> None:
    ok, warnings = validate_prep_inputs(
        _req(_REAL_CV, _REAL_JD, "$"),
        cv_text=_REAL_CV,
    )
    assert ok is True
    assert any("company name" in w for w in warnings)


def test_validate_all_real_no_warnings() -> None:
    ok, warnings = validate_prep_inputs(
        _req(_REAL_CV, _REAL_JD, "Acme Payments"),
        cv_text=_REAL_CV,
    )
    assert ok is True
    assert warnings == []
