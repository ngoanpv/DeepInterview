"""Server-side CV/résumé document extraction (PDF/DOCX/HTML -> plain text).

THE BUG this fixes: an uploaded CV reaches prep as either a ``data:`` URL of raw
file bytes or an ``http(s)`` URL pointing at a PDF/DOCX. The old ``fetch_cv`` did
``resp.text`` on those bytes, so the "CV" was binary garbage — validation flagged
it and prep fell back to a mock candidate.

:func:`extract_cv_text` resolves the document to real text:

* plain text (the paste path) is returned verbatim — no parsing;
* a ``data:`` URL is base64-decoded to ``(bytes, mime)``;
* an ``http(s)`` URL is fetched to ``(bytes, content_type)`` (on fetch failure we
  fall back to treating the URL string itself as the document text, preserving
  the offline-tolerant behaviour the prep tests rely on);
* bytes are converted with Microsoft **markitdown** (in a worker thread), and if
  that yields empty/garbage AND a Gemini key is configured, **Gemini** native
  multimodal document understanding is the fallback for scanned/image PDFs.

It is best-effort and never raises: the worst case returns ``("", [warning])`` so
prep proceeds with limited candidate info rather than crashing.

Heavy/optional SDKs (markitdown, google-genai) are lazy-imported INSIDE the
helpers, so this module imports cleanly even when they aren't installed.
"""

from __future__ import annotations

import asyncio
import base64
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from ..core.logging import get_logger
from ..core.validation import assess_text

if TYPE_CHECKING:
    from ..core.deps import Deps

__all__ = ["extract_cv_text"]

log = get_logger(__name__)

# Keep the document fetch tight so an unreachable host fails fast offline.
_CV_FETCH_TIMEOUT_SEC = 5.0

# Minimum length for an extraction to count as "meaningful" content.
_MIN_CV_LEN = 30

_UNREADABLE_WARNING = (
    "Couldn't read the uploaded CV file — proceeding with limited candidate info."
)

# Map common document MIME types to the file suffix markitdown keys conversion on.
_MIME_SUFFIX = {
    "application/pdf": ".pdf",
    "application/x-pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".docx",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "text/html": ".html",
    "application/xhtml+xml": ".html",
}

# Gemini extraction prompt: text only, no commentary, so it round-trips cleanly.
_GEMINI_PROMPT = (
    "Extract the full plain-text content of this résumé/CV. "
    "Output only the text, no commentary."
)


def _suffix_for_mime(mime: str) -> str:
    """Best file suffix for ``mime`` (defaults to ``.txt`` for unknown types)."""
    base = (mime or "").split(";", 1)[0].strip().lower()
    return _MIME_SUFFIX.get(base, ".txt")


def _is_meaningful(text: str) -> bool:
    """True if ``text`` reads like real CV content (reuses the prep heuristics)."""
    ok, _ = assess_text(text, kind="cv", min_len=_MIN_CV_LEN)
    return ok


def _markitdown_extract(data: bytes, mime: str) -> str:
    """Convert document ``data`` to text via markitdown (blocking; run in a thread).

    Lazy-imports markitdown so the module imports without it installed. Writes the
    bytes to a temp file with a mime-derived suffix (markitdown dispatches on the
    extension) and returns the converted text, or ``""`` on any failure.
    """
    try:
        from markitdown import MarkItDown  # noqa: PLC0415 - optional, lazy
    except ImportError as exc:  # pragma: no cover - depends on optional dep
        log.warning("markitdown is not installed; cannot parse CV document (%s)", exc)
        return ""

    suffix = _suffix_for_mime(mime)
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        result = MarkItDown().convert(tmp_path)
        return (result.text_content or "").strip()
    except Exception as exc:  # noqa: BLE001 - best-effort: any failure -> empty
        log.warning("markitdown conversion failed (%s)", exc)
        return ""
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:  # pragma: no cover - cleanup is advisory only
                pass


async def _gemini_extract(data: bytes, mime: str, deps: Deps) -> str:
    """Extract CV text from raw bytes via Gemini native multimodal (lazy import).

    Used only as a fallback when markitdown yields nothing (e.g. scanned/image
    PDFs). Returns ``""`` on any failure so the caller degrades gracefully.
    """
    settings = deps.settings
    try:
        from google import genai  # noqa: PLC0415 - optional, lazy
        from google.genai import types  # noqa: PLC0415 - optional, lazy
    except ImportError as exc:  # pragma: no cover - depends on optional SDK
        log.warning("google-genai is not installed; skipping Gemini CV fallback (%s)", exc)
        return ""

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        resp = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=[
                types.Part.from_bytes(data=data, mime_type=mime or "application/pdf"),
                _GEMINI_PROMPT,
            ],
        )
        return (resp.text or "").strip()
    except Exception as exc:  # noqa: BLE001 - best-effort: any failure -> empty
        log.warning("Gemini CV extraction failed (%s)", exc)
        return ""


def _decode_data_url(cv_url: str) -> tuple[bytes, str] | None:
    """Decode a ``data:<mime>;base64,<b64>`` URL to ``(bytes, mime)``; else ``None``."""
    if not cv_url.startswith("data:"):
        return None
    try:
        header, _, payload = cv_url[len("data:") :].partition(",")
        if not payload:
            return None
        meta = header.split(";")
        mime = meta[0] if meta and meta[0] else "application/octet-stream"
        is_base64 = "base64" in meta[1:]
        if is_base64:
            data = base64.b64decode(payload, validate=False)
        else:
            # Percent-encoded text data URL (rare for CVs, but handle it).
            from urllib.parse import unquote_to_bytes  # noqa: PLC0415

            data = unquote_to_bytes(payload)
        return data, mime
    except Exception as exc:  # noqa: BLE001 - malformed data URL -> not a document
        log.warning("could not decode data: CV URL (%s)", exc)
        return None


def _is_fetchable_url(url: str) -> bool:
    """SSRF guard for the user-supplied CV URL.

    Only http(s), and never loopback/private/link-local hosts — the fetch runs
    server-side, so an attacker-chosen URL could otherwise probe the internal
    network (e.g. a metadata service or the lightrag sidecar) with the response
    reflected into the readable session view. Hostname-literal checks only (no
    DNS resolution); pair with network egress policy for defence in depth. A
    refused URL degrades exactly like an unreachable one (caller falls back to
    treating the input as pasted text).
    """
    import ipaddress  # noqa: PLC0415
    from urllib.parse import urlsplit  # noqa: PLC0415

    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.scheme not in ("http", "https"):
        return False
    host = (parts.hostname or "").strip("[]").lower()
    if not host or host == "localhost" or host.endswith((".localhost", ".internal")):
        return False
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return True  # non-IP hostname: allowed (see docstring caveat)
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


async def _fetch_url_bytes(cv_url: str) -> tuple[bytes, str] | None:
    """GET ``cv_url`` returning ``(bytes, content_type)``; ``None`` on any failure."""
    if not _is_fetchable_url(cv_url):
        log.warning("fetch_cv: refusing non-public URL %r", cv_url)
        return None
    try:
        async with httpx.AsyncClient(timeout=_CV_FETCH_TIMEOUT_SEC) as client:
            resp = await client.get(cv_url, follow_redirects=True)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            return resp.content, content_type
    except Exception as exc:  # noqa: BLE001 - best-effort: fetch failure -> caller falls back
        log.warning("fetch_cv: could not GET %r (%s)", cv_url, exc)
        return None


async def _extract_from_bytes(data: bytes, mime: str, deps: Deps) -> tuple[str, list[str]]:
    """Convert document ``data`` to text: markitdown first, Gemini fallback.

    Returns ``(text, warnings)``. On total failure returns ``("", [warning])`` —
    never the raw bytes/base64, which would feed garbage into ``cv_analysis``.
    """
    text = await asyncio.to_thread(_markitdown_extract, data, mime)
    if text and _is_meaningful(text):
        return text, []

    # Fallback: native multimodal document understanding for scanned/image PDFs.
    settings = deps.settings
    gemini_ready = bool(settings.gemini_api_key) and (
        (settings.llm_provider or "").lower() == "gemini"
    )
    if gemini_ready:
        fallback = await _gemini_extract(data, mime, deps)
        if fallback and _is_meaningful(fallback):
            return fallback, []

    # markitdown gave us *something* but it didn't pass the meaningfulness bar;
    # still prefer it over nothing (downstream validation makes the final call).
    if text:
        return text, []

    return "", [_UNREADABLE_WARNING]


async def extract_cv_text(cv_url: str, deps: Deps) -> tuple[str, list[str]]:
    """Resolve ``cv_url`` to plain CV text. Returns ``(text, warnings)``.

    Dispatch:

    * ``data:`` URL  -> base64-decode -> parse bytes (markitdown / Gemini);
    * ``http(s)`` URL -> GET bytes -> parse; on fetch failure fall back to using
      the URL string itself as the document text (offline-tolerant, no warning);
    * anything else  -> the paste path: return the text verbatim, no parsing.

    Best-effort and never raises.
    """
    if not cv_url:
        return "", []

    # 1) data: URL of raw file bytes (the no-R2 upload path).
    decoded = _decode_data_url(cv_url)
    if decoded is not None:
        data, mime = decoded
        return await _extract_from_bytes(data, mime, deps)

    # 2) http(s) URL pointing at a document (the R2 / hosted-file path).
    stripped = cv_url.strip()
    if stripped.lower().startswith(("http://", "https://")) and "\n" not in stripped:
        fetched = await _fetch_url_bytes(stripped)
        if fetched is None:
            # Fetch failed: the URL string is still a meaningful pointer. Preserve
            # the legacy behaviour the offline prep test depends on (no warning).
            return cv_url, []
        data, content_type = fetched
        text, warnings = await _extract_from_bytes(data, content_type, deps)
        if text:
            return text, warnings
        # Couldn't parse the fetched bytes: fall back to the URL as the pointer.
        return cv_url, warnings

    # 3) Plain text — the paste path. Return verbatim, no parsing.
    return cv_url, []
