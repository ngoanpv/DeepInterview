"""Local-first tracing for agent work (WP-12).

Two sinks, both best-effort and never raising:

- **Local JSONL (default ON):** every :func:`start_trace` writes
  ``<trace_dir>/<trace_id>.jsonl`` — one JSON object per line
  (``trace_start`` / ``span_start`` / ``span_end`` / ``event`` / ``llm_call`` /
  ``trace_end``). Readable offline via the ``deepinterview traces`` CLI and
  ``GET /api/traces``. No extra dependencies.
- **Langfuse (opt-in):** when ``LANGFUSE_*`` keys are set and the
  ``observability`` extra is installed, spans are additionally emitted as
  OpenTelemetry spans, which Langfuse v4 captures automatically once its
  client is constructed in :func:`init_tracing`. Missing SDK ⇒ skipped.

Gating: :func:`is_enabled` is the single switch. Resolution order is
explicit overrides (tests / :func:`init_tracing` from Settings at process
start) → ``TRACE_ENABLED`` env → default ON. The test suite sets
``TRACE_ENABLED=0`` (see ``tests/conftest.py``), so the offline suite writes
nothing unless a test opts in with :func:`init_tracing`.

Context tracking uses :mod:`contextvars`, so concurrent prep/score runs and
async tasks each keep their own trace/span stack.
"""

from __future__ import annotations

import contextlib
import functools
import json
import os
import threading
import time
import uuid
from collections.abc import Iterator
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .logging import get_logger

log = get_logger(__name__)

# --- configuration (overrides win over env, env wins over defaults) ----------

_overrides: dict[str, Any] = {}
_langfuse_client: Any | None = None
_otel_tracer: Any | None = None
_write_lock = threading.Lock()


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", ""}


def init_tracing(
    *,
    enabled: bool | None = None,
    trace_dir: str | Path | None = None,
    include_prompts: bool | None = None,
    langfuse_public_key: str | None = None,
    langfuse_secret_key: str | None = None,
    langfuse_host: str | None = None,
) -> None:
    """Configure tracing (idempotent, never raises).

    Called once at process start from ``observability.init_observability``
    with Settings values; tests call it directly with a ``tmp_path`` dir.
    ``None`` means "leave the current value" (env still applies underneath).
    Also attempts the Langfuse client construction so its OTel exporter
    captures the spans emitted alongside the JSONL events.
    """
    try:
        if enabled is not None:
            _overrides["enabled"] = bool(enabled)
        if trace_dir is not None:
            _overrides["dir"] = str(trace_dir)
        if include_prompts is not None:
            _overrides["include_prompts"] = bool(include_prompts)
        _init_langfuse(
            public_key=langfuse_public_key or os.environ.get("LANGFUSE_PUBLIC_KEY"),
            secret_key=langfuse_secret_key or os.environ.get("LANGFUSE_SECRET_KEY"),
            host=langfuse_host or os.environ.get("LANGFUSE_HOST"),
        )
    except Exception as exc:  # noqa: BLE001 - tracing config must never break boot
        log.warning("tracing init failed (%s); continuing without tracing", exc)


def reset_tracing() -> None:
    """Clear programmatic overrides (tests) and drop the Langfuse client."""
    global _langfuse_client, _otel_tracer
    _overrides.clear()
    _langfuse_client = None
    _otel_tracer = None
    _current_trace.set(None)
    _span_stack.set(())


def is_enabled() -> bool:
    if "enabled" in _overrides:
        return bool(_overrides["enabled"])
    return _env_flag("TRACE_ENABLED", True)


def trace_dir() -> Path:
    raw = _overrides.get("dir") or os.environ.get("TRACE_DIR") or ".deepinterview/traces"
    return Path(raw)


def _include_prompts() -> bool:
    if "include_prompts" in _overrides:
        return bool(_overrides["include_prompts"])
    return _env_flag("TRACE_INCLUDE_PROMPTS", False)


def _init_langfuse(*, public_key: str | None, secret_key: str | None, host: str | None) -> None:
    """Best-effort Langfuse client construction (enables OTel forwarding)."""
    global _langfuse_client
    if not (public_key and secret_key):
        return
    try:
        from langfuse import Langfuse  # lazy: optional `observability` extra
    except ImportError:
        log.debug("langfuse not installed; local JSONL tracing only")
        return
    try:
        kwargs: dict[str, Any] = {"public_key": public_key, "secret_key": secret_key}
        if host:
            kwargs["host"] = host
        _langfuse_client = Langfuse(**kwargs)
        log.info("Langfuse tracing enabled (local JSONL + hosted traces)")
    except Exception as exc:  # noqa: BLE001 - hosted tracing is strictly optional
        log.warning("Langfuse init failed (%s); local JSONL tracing only", exc)
        _langfuse_client = None


def _otel() -> Any | None:
    """Lazily resolve the OTel tracer (None when SDK/Langfuse absent)."""
    global _otel_tracer
    if _otel_tracer is not None:
        return _otel_tracer
    if _langfuse_client is None:
        return None
    try:
        from opentelemetry import trace as otel_trace  # part of langfuse's deps

        _otel_tracer = otel_trace.get_tracer("deepinterview")
        return _otel_tracer
    except Exception:  # noqa: BLE001 - OTel is optional
        return None


def langfuse_trace_url(trace_id: str) -> str | None:
    """Hosted URL for a trace, or None when Langfuse is not configured."""
    if _langfuse_client is None:
        return None
    try:
        return _langfuse_client.get_trace_url(trace_id)
    except Exception:  # noqa: BLE001 - informational only
        return None


# --- trace / span context -----------------------------------------------------

_BORING_ATTRS = {"session_id"}


@dataclass
class _TraceInfo:
    trace_id: str
    name: str
    session_id: str | None
    start_ts: str
    start_perf: float


@dataclass
class _SpanInfo:
    span_id: str
    trace_id: str
    parent_id: str | None
    name: str
    start_perf: float
    otel_cm: Any | None = None
    otel_span: Any | None = None


_current_trace: ContextVar[_TraceInfo | None] = ContextVar("di_trace", default=None)
_span_stack: ContextVar[tuple[_SpanInfo, ...]] = ContextVar("di_spans", default=())


def current_trace_id() -> str | None:
    t = _current_trace.get()
    return t.trace_id if t is not None else None


def current_session_id() -> str | None:
    t = _current_trace.get()
    return t.session_id if t is not None else None


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _new_trace_id() -> str:
    return "tr_" + uuid.uuid4().hex[:12]


def _new_span_id() -> str:
    return "sp_" + uuid.uuid4().hex[:8]


def _trace_path(trace_id: str, *, directory: Path | None = None) -> Path:
    return (directory or trace_dir()) / f"{trace_id}.jsonl"


def _append_event(event: dict[str, Any], *, directory: Path | None = None) -> None:
    """Append one event line; creates the dir on first write. Never raises."""
    try:
        d = directory or trace_dir()
        d.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, default=str)
        with _write_lock, open(d / f"{event['trace_id']}.jsonl", "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception as exc:  # noqa: BLE001 - tracing must never break a run
        log.debug("tracing write failed (%s)", exc)


def _otel_start(name: str, attrs: dict[str, Any]) -> tuple[Any | None, Any | None]:
    """Enter an OTel span alongside the JSONL one (None when unavailable)."""
    tracer = _otel()
    if tracer is None:
        return None, None
    try:
        cm = tracer.start_as_current_span(name)
        span = cm.__enter__()
        try:
            for k, v in attrs.items():
                span.set_attribute(k, str(v)[:500])
        except Exception:  # noqa: BLE001, S110 - attributes are advisory
            pass
        return cm, span
    except Exception:  # noqa: BLE001 - OTel is optional
        return None, None


def _otel_end(cm: Any | None, span: Any | None, *, status: str, error: str | None) -> None:
    if cm is None:
        return
    try:
        if span is not None and error:
            try:
                span.set_attribute("error", error[:500])
            except Exception:  # noqa: BLE001, S110 - advisory
                pass
        cm.__exit__(None, None, None)
    except Exception as exc:  # noqa: BLE001 - OTel is optional
        log.debug("otel span close failed (%s)", exc)


@contextlib.contextmanager
def start_trace(
    name: str, *, session_id: str | None = None, metadata: dict[str, Any] | None = None
) -> Iterator[str]:
    """Open a trace; yields its id. Nested traces reuse the outer one.

    When disabled this yields a throwaway id and writes nothing, so call
    sites need no ``is_enabled()`` guards of their own.
    """
    if not is_enabled():
        yield "tr_disabled"
        return
    outer = _current_trace.get()
    if outer is not None:
        # Nested: attribute work to the outer trace instead of fragmenting.
        yield outer.trace_id
        return
    trace_id = _new_trace_id()
    info = _TraceInfo(
        trace_id=trace_id,
        name=name,
        session_id=session_id,
        start_ts=_utc_now(),
        start_perf=time.perf_counter(),
    )
    token = _current_trace.set(info)
    _append_event(
        {
            "type": "trace_start",
            "trace_id": trace_id,
            "name": name,
            "session_id": session_id,
            "ts": info.start_ts,
            "metadata": metadata or {},
        }
    )
    status, error = "ok", None
    try:
        yield trace_id
    except Exception as exc:
        status, error = "error", f"{type(exc).__name__}: {exc}"
        raise
    finally:
        duration_ms = (time.perf_counter() - info.start_perf) * 1000
        _append_event(
            {
                "type": "trace_end",
                "trace_id": trace_id,
                "name": name,
                "session_id": session_id,
                "ts": _utc_now(),
                "duration_ms": round(duration_ms, 1),
                "status": status,
                **({"error": error[:500]} if error else {}),
            }
        )
        try:
            _current_trace.reset(token)
        except ValueError:
            # A LiveKit job opens its trace in the entrypoint task but runs
            # shutdown callbacks in a separate asyncio Context. ContextVar
            # tokens may only be reset in the Context that created them, so a
            # cross-context close would otherwise raise here *after* writing
            # trace_end and abort the caller's shutdown work. Clear only when
            # this Context inherited the same trace; never disturb an unrelated
            # trace that may already be active in the closing Context.
            if _current_trace.get() is info:
                _current_trace.set(outer)


@contextlib.contextmanager
def start_span(name: str, **attrs: Any) -> Iterator[str]:
    """Open a span in the current trace (auto-starts an ``auto`` trace when
    none is active). Yields the span id; writes nothing when disabled."""
    if not is_enabled():
        yield "sp_disabled"
        return
    if _current_trace.get() is None:
        with start_trace("auto"), start_span(name, **attrs) as span_id:
            yield span_id
        return
    trace = _current_trace.get()
    assert trace is not None
    stack = _span_stack.get()
    parent_id = stack[-1].span_id if stack else None
    span_id = _new_span_id()
    otel_cm, otel_span = _otel_start(name, {"trace_id": trace.trace_id, **attrs})
    info = _SpanInfo(
        span_id=span_id,
        trace_id=trace.trace_id,
        parent_id=parent_id,
        name=name,
        start_perf=time.perf_counter(),
        otel_cm=otel_cm,
        otel_span=otel_span,
    )
    token = _span_stack.set(stack + (info,))
    _append_event(
        {
            "type": "span_start",
            "trace_id": trace.trace_id,
            "span_id": span_id,
            "parent_id": parent_id,
            "name": name,
            "ts": _utc_now(),
            "attrs": attrs,
        }
    )
    status, error = "ok", None
    try:
        yield span_id
    except Exception as exc:
        status, error = "error", f"{type(exc).__name__}: {exc}"
        raise
    finally:
        duration_ms = (time.perf_counter() - info.start_perf) * 1000
        _append_event(
            {
                "type": "span_end",
                "trace_id": trace.trace_id,
                "span_id": span_id,
                "name": name,
                "ts": _utc_now(),
                "duration_ms": round(duration_ms, 1),
                "status": status,
                **({"error": error[:500]} if error else {}),
            }
        )
        _otel_end(otel_cm, otel_span, status=status, error=error)
        _span_stack.reset(token)


def add_event(name: str, attrs: dict[str, Any] | None = None) -> None:
    """Record a point-in-time event on the current span/trace (no-op offline)."""
    if not is_enabled():
        return
    trace = _current_trace.get()
    if trace is None:
        return
    stack = _span_stack.get()
    try:
        _append_event(
            {
                "type": "event",
                "trace_id": trace.trace_id,
                "span_id": stack[-1].span_id if stack else None,
                "name": name,
                "ts": _utc_now(),
                "attrs": attrs or {},
            }
        )
    except Exception:  # noqa: BLE001, S110 - tracing never raises
        pass


def record_llm_call(
    *,
    provider: str,
    model: str,
    method: str,
    schema: str = "",
    prompt_chars: int = 0,
    latency_ms: float = 0.0,
    ok: bool = True,
    error: str | None = None,
    prompt_preview: str = "",
) -> None:
    """Record one LLM completion (lengths always; prompt text only when opted in)."""
    if not is_enabled():
        return
    trace = _current_trace.get()
    if trace is None:
        return
    stack = _span_stack.get()
    try:
        event: dict[str, Any] = {
            "type": "llm_call",
            "trace_id": trace.trace_id,
            "span_id": stack[-1].span_id if stack else None,
            "ts": _utc_now(),
            "provider": provider,
            "model": model,
            "method": method,
            "schema": schema,
            "prompt_chars": prompt_chars,
            "latency_ms": round(latency_ms, 1),
            "ok": ok,
        }
        if error:
            event["error"] = error[:500]
        if prompt_preview and _include_prompts():
            event["prompt_preview"] = prompt_preview[:500]
        _append_event(event)
    except Exception:  # noqa: BLE001, S110 - tracing never raises
        pass


def traced(name: str | None = None):
    """Decorator for async pipeline functions: run inside a named span."""

    def deco(fn):
        span_name = name or f"{fn.__module__}.{fn.__qualname__}"

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            with start_span(span_name):
                return await fn(*args, **kwargs)

        return wrapper

    return deco


# --- LLM wrapper --------------------------------------------------------------


class TracedLLM:
    """An :class:`LLMAdapter` decorator that records timing + outcome per call.

    Wraps whatever adapter ``get_llm`` returned (mock included — mock calls
    show up as near-zero-latency spans, which keeps traces complete offline).
    Full prompt text is never stored unless ``TRACE_INCLUDE_PROMPTS=1``.
    """

    def __init__(self, inner: Any, *, provider: str = "") -> None:
        self._inner = inner
        self._provider = provider or type(inner).__name__.replace("LLM", "").lower() or "mock"
        self._model = getattr(inner, "_model", "") or ""

    def __getattr__(self, item: str) -> Any:
        return getattr(self._inner, item)

    async def complete_text(self, *, system: str, user: str) -> str:
        t0 = time.perf_counter()
        with start_span("llm.complete_text", provider=self._provider, model=self._model):
            try:
                result = await self._inner.complete_text(system=system, user=user)
            except Exception as exc:
                record_llm_call(
                    provider=self._provider,
                    model=self._model,
                    method="complete_text",
                    prompt_chars=len(system) + len(user),
                    latency_ms=(time.perf_counter() - t0) * 1000,
                    ok=False,
                    error=f"{type(exc).__name__}: {exc}",
                    prompt_preview=f"{system}\n{user}",
                )
                raise
            record_llm_call(
                provider=self._provider,
                model=self._model,
                method="complete_text",
                prompt_chars=len(system) + len(user),
                latency_ms=(time.perf_counter() - t0) * 1000,
                ok=True,
                prompt_preview=f"{system}\n{user}",
            )
            return result

    async def complete_json(self, *, system: str, user: str, schema: type) -> Any:
        schema_name = getattr(schema, "__name__", str(schema))
        t0 = time.perf_counter()
        with start_span(
            "llm.complete_json",
            provider=self._provider,
            model=self._model,
            schema=schema_name,
        ):
            try:
                result = await self._inner.complete_json(system=system, user=user, schema=schema)
            except Exception as exc:
                record_llm_call(
                    provider=self._provider,
                    model=self._model,
                    method="complete_json",
                    schema=schema_name,
                    prompt_chars=len(system) + len(user),
                    latency_ms=(time.perf_counter() - t0) * 1000,
                    ok=False,
                    error=f"{type(exc).__name__}: {exc}",
                    prompt_preview=f"{system}\n{user}",
                )
                raise
            record_llm_call(
                provider=self._provider,
                model=self._model,
                method="complete_json",
                schema=schema_name,
                prompt_chars=len(system) + len(user),
                latency_ms=(time.perf_counter() - t0) * 1000,
                ok=True,
                prompt_preview=f"{system}\n{user}",
            )
            return result


# --- reading traces back (CLI + API share these) ------------------------------


@dataclass
class TraceSummary:
    trace_id: str
    name: str
    session_id: str | None
    started_at: str
    duration_ms: float | None
    spans: int
    llm_calls: int
    errors: int
    status: str


def _iter_events(trace_id: str, *, directory: Path | None = None) -> Iterator[dict[str, Any]]:
    path = _trace_path(trace_id, directory=directory)
    if not path.exists():
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def read_trace(trace_id: str, *, directory: Path | None = None) -> dict[str, Any] | None:
    """Full event log for one trace (spans nested for display), or None."""
    if not trace_id or "/" in trace_id or trace_id.startswith("."):
        return None
    events = list(_iter_events(trace_id, directory=directory))
    if not events:
        return None
    summary = summarize_events(trace_id, events)
    spans: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for ev in events:
        if ev.get("type") == "span_start":
            spans[ev["span_id"]] = {
                "span_id": ev["span_id"],
                "parent_id": ev.get("parent_id"),
                "name": ev.get("name"),
                "started_at": ev.get("ts"),
                "attrs": ev.get("attrs", {}),
                "events": [],
                "llm_calls": [],
                "duration_ms": None,
                "status": "running",
            }
            order.append(ev["span_id"])
        elif ev.get("type") == "span_end" and ev.get("span_id") in spans:
            spans[ev["span_id"]].update(
                duration_ms=ev.get("duration_ms"),
                status=ev.get("status", "ok"),
                **({"error": ev["error"]} if ev.get("error") else {}),
            )
        elif ev.get("type") in {"event", "llm_call"}:
            sid = ev.get("span_id")
            if sid in spans:
                key = "llm_calls" if ev["type"] == "llm_call" else "events"
                spans[sid][key].append(ev)
    # Nest into a tree for the viewer.
    children: dict[str | None, list[dict[str, Any]]] = {}
    for sid in order:
        children.setdefault(spans[sid]["parent_id"], []).append(spans[sid])
    summary["spans"] = children.get(None, [])
    summary["all_spans_flat"] = [spans[sid] for sid in order]
    summary["events"] = [e for e in events if e.get("type") == "event" and not e.get("span_id")]
    summary["langfuse_url"] = langfuse_trace_url(trace_id)
    return summary


def summarize_events(trace_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate one event list into a header dict (shared by list + detail)."""
    name, session_id, started_at = trace_id, None, ""
    duration_ms: float | None = None
    status = "running"
    spans = llm_calls = errors = 0
    for ev in events:
        t = ev.get("type")
        if t == "trace_start":
            name = ev.get("name", name)
            session_id = ev.get("session_id")
            started_at = ev.get("ts", "")
        elif t == "trace_end":
            duration_ms = ev.get("duration_ms")
            status = ev.get("status", "ok")
            if ev.get("error"):
                errors += 1
        elif t == "span_start":
            spans += 1
        elif t == "span_end" and ev.get("status") == "error":
            errors += 1
        elif t == "llm_call":
            llm_calls += 1
            if not ev.get("ok", True):
                errors += 1
    return {
        "trace_id": trace_id,
        "name": name,
        "session_id": session_id,
        "started_at": started_at,
        "duration_ms": duration_ms,
        "spans": spans,
        "llm_calls": llm_calls,
        "errors": errors,
        "status": status,
    }


def list_traces(
    *, directory: Path | None = None, session_id: str | None = None, limit: int = 20
) -> list[dict[str, Any]]:
    """Newest-first trace headers (bounded scan; skips malformed files)."""
    d = directory or trace_dir()
    if not d.exists():
        return []
    try:
        files = sorted(d.glob("tr_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for path in files:
        try:
            with open(path, encoding="utf-8") as fh:
                events = [json.loads(line) for line in fh if line.strip()]
        except (OSError, json.JSONDecodeError):
            continue
        header = summarize_events(path.stem, events)
        if session_id and header["session_id"] != session_id:
            continue
        header["langfuse_url"] = None  # list stays offline-cheap; detail resolves it
        out.append(header)
        if len(out) >= max(1, limit):
            break
    return out


__all__ = [
    "TracedLLM",
    "add_event",
    "current_session_id",
    "current_trace_id",
    "init_tracing",
    "is_enabled",
    "langfuse_trace_url",
    "list_traces",
    "read_trace",
    "record_llm_call",
    "reset_tracing",
    "start_span",
    "start_trace",
    "trace_dir",
    "traced",
]
