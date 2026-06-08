"""WP-12 — gated, provider-agnostic observability for the agent.

Design (see docs/DEPLOY.md):
  - ZERO config = clean no-op. With no ``SENTRY_DSN`` / ``LANGFUSE_*`` set,
    nothing initializes and nothing heavy is imported.
  - ``sentry-sdk`` and ``langfuse`` are the optional ``observability`` extra
    (NOT installed by default). Imports are lazy + wrapped in ``try/except
    ImportError`` so a missing package is a silent no-op.
  - Never raises: tracing must never break a prep run or a live turn.

This module is intentionally NOT wired into ``app.py`` / ``worker.py`` so the
default offline path stays dependency-free. To enable tracing, install the
extra and call :func:`init_observability` at process start, e.g.::

    # apps/agent/src/deepinterview_agent/app.py
    from .core.observability import init_observability
    init_observability(get_settings())

    # apps/agent/src/deepinterview_agent/worker.py (entrypoint)
    init_observability(get_settings())

Install the extra with::  uv sync --extra observability
and set ``SENTRY_DSN`` and/or ``LANGFUSE_PUBLIC_KEY`` + ``LANGFUSE_SECRET_KEY``.
"""

from __future__ import annotations

import os
from typing import Any, Protocol

from .logging import get_logger

_log = get_logger("deepinterview.observability")

_initialized = False


class _Settings(Protocol):
    """Structural type — anything exposing these optional attrs works.

    The agent ``Settings`` (core/config.py) does not yet declare Sentry/Langfuse
    fields; we read them from the environment as a fallback so this module works
    with or without those fields being added later.
    """


def _env(*names: str) -> str | None:
    for name in names:
        val = os.environ.get(name)
        if val:
            return val
    return None


def _sentry_dsn(settings: Any | None) -> str | None:
    return getattr(settings, "sentry_dsn", None) or _env("SENTRY_DSN")


def _langfuse_keys(settings: Any | None) -> tuple[str | None, str | None]:
    public = getattr(settings, "langfuse_public_key", None) or _env("LANGFUSE_PUBLIC_KEY")
    secret = getattr(settings, "langfuse_secret_key", None) or _env("LANGFUSE_SECRET_KEY")
    return public, secret


def init_observability(settings: Any | None = None) -> None:
    """Initialize Sentry and/or Langfuse if configured. No-op otherwise.

    Safe to call multiple times and safe to call with the optional packages not
    installed (logs a debug line and returns).
    """
    global _initialized
    if _initialized:
        return
    _initialized = True  # mark first so a failure doesn't loop on retry.

    dsn = _sentry_dsn(settings)
    if dsn:
        try:
            import sentry_sdk  # noqa: PLC0415

            sentry_sdk.init(
                dsn=dsn,
                traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
                environment=os.environ.get("NODE_ENV", "production"),
            )
            _log.info("Sentry initialized")
        except ImportError:
            _log.debug("sentry-sdk not installed; skipping Sentry (extra: observability)")
        except Exception as exc:  # pragma: no cover - defensive
            _log.warning("Sentry init failed: %s", exc)

    public, secret = _langfuse_keys(settings)
    if public and secret:
        try:
            import langfuse  # noqa: F401, PLC0415

            _log.info("Langfuse credentials present; LLM tracing available")
        except ImportError:
            _log.debug("langfuse not installed; skipping (extra: observability)")
        except Exception as exc:  # pragma: no cover - defensive
            _log.warning("Langfuse init failed: %s", exc)


class _NoOpTracer:
    """Fallback tracer with the minimal surface used by call sites."""

    def start_span(self, _name: str, **_kw: Any) -> "_NoOpSpan":
        return _NoOpSpan()


class _NoOpSpan:
    def __enter__(self) -> "_NoOpSpan":
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False

    def set_attribute(self, _key: str, _value: Any) -> None:
        return None


def get_tracer() -> _NoOpTracer:
    """Return a tracer. Currently always the no-op fallback.

    Provided so call sites can `with get_tracer().start_span(...)` unconditionally;
    swap the implementation here once a real tracing provider is wired in.
    """
    return _NoOpTracer()


def capture_error(error: BaseException) -> None:
    """Report an error to Sentry if available; else log it. Never raises."""
    dsn = _sentry_dsn(None)
    if dsn:
        try:
            import sentry_sdk  # noqa: PLC0415

            sentry_sdk.capture_exception(error)
            return
        except ImportError:
            pass
        except Exception:  # pragma: no cover - defensive
            pass
    _log.error("capture_error: %r", error)
