"""Hard cost / duration guard for the live interview (Golden Rule #5).

REQUIRES the optional ``livekit-agents`` extra at runtime (it is started from
the worker), but its only hard dependency is ``asyncio`` + the livekit-free
``state`` module: it talks to the running session through a tiny duck-typed
surface (``say`` / ``shutdown``), so it is fully unit-testable with a fake
session and a fake clock.

The :class:`SessionGuard` runs OFF the turn-critical path as a fire-and-forget
asyncio task (like :class:`~deepinterview_agent.live.director.Director`). It
enforces two ceilings — wall-clock duration and total transcript turns — and,
when either is reached, says a brief closing line and shuts the session down
gracefully (draining), which triggers the worker's persist + score shutdown
callback. The web layer caps interview *creation* per tier; this is the in-room
backstop so a stalled or looping model can never run a voice session unbounded.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import TYPE_CHECKING, Callable

from ..core.logging import get_logger

if TYPE_CHECKING:
    from .state import InterviewUserdata

log = get_logger(__name__)

_WRAP_UP_LINE = (
    "We're at time for this interview, so let's wrap up here. "
    "Thank you — your feedback will be ready shortly."
)


class SessionGuard:
    """Enforce hard duration/turn ceilings on a live session; never blocks a turn.

    ``session`` only needs an async ``say(text)`` and a ``shutdown(*, drain)``
    method (the livekit ``AgentSession`` surface), so tests can pass a fake.
    ``time_fn`` defaults to :func:`time.monotonic` and is injectable for tests.
    """

    def __init__(
        self,
        session: object,
        userdata: InterviewUserdata,
        *,
        max_duration_sec: float,
        max_turns: int,
        interval_sec: float = 2.0,
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        self._session = session
        self._ud = userdata
        self._max_duration = float(max_duration_sec)
        self._max_turns = int(max_turns)
        self._interval = interval_sec
        self._time = time_fn or time.monotonic
        self._task: asyncio.Task[None] | None = None
        self._started_at: float = 0.0
        self.tripped: bool = False

    def start(self) -> None:
        """Launch the guard as a detached background task (idempotent)."""
        if self._task is None:
            self._started_at = self._time()
            self._task = asyncio.create_task(self._run())

    async def aclose(self) -> None:
        """Stop the guard (idempotent)."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    def _limit_reached(self, elapsed: float) -> str | None:
        """Return a human reason if a ceiling is hit, else ``None``."""
        if elapsed >= self._max_duration:
            return f"max duration {self._max_duration:.0f}s reached"
        turns = len(self._ud.transcript)
        if turns >= self._max_turns:
            return f"max turns {self._max_turns} reached"
        return None

    async def _wrap_up(self, reason: str) -> None:
        """Say a closing line (best-effort) then shut the session down gracefully."""
        log.warning("session_guard: %s for %s — wrapping up", reason, self._ud.session_id)
        with contextlib.suppress(Exception):
            await self._session.say(_WRAP_UP_LINE)  # type: ignore[attr-defined]
        with contextlib.suppress(Exception):
            self._session.shutdown(drain=True)  # type: ignore[attr-defined]

    async def _run(self) -> None:
        try:
            while True:
                reason = self._limit_reached(self._time() - self._started_at)
                if reason is not None:
                    self.tripped = True
                    await self._wrap_up(reason)
                    return
                await asyncio.sleep(self._interval)
        except asyncio.CancelledError:  # pragma: no cover - cancellation path
            raise
        except Exception:  # noqa: BLE001 - a guard must never crash the call
            log.exception("session_guard: watcher error (ignored)")
