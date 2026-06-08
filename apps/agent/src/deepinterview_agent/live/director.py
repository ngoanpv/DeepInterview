"""Background coverage watcher for the live interview.

REQUIRES the optional ``livekit-agents`` extra at runtime (it is started from the
worker), but its only hard dependency is ``asyncio`` + the livekit-free
``state`` module. It is kept here (not in ``state.py``) because it is part of the
live runtime, and ``live/__init__.py`` must not pull it in.

The :class:`Director` runs OFF the turn-critical path as a fire-and-forget
asyncio task. It periodically samples how far the interview has progressed
through the plan and updates a coverage pointer / logs it. It never awaits on the
turn loop and never mutates shared interview state, so it cannot block or corrupt
a turn — it only observes.
"""

from __future__ import annotations

import asyncio
import contextlib

from ..core.logging import get_logger
from . import state
from .state import InterviewUserdata

log = get_logger(__name__)


class Director:
    """Observes plan coverage in the background; never blocks a turn."""

    def __init__(self, userdata: InterviewUserdata, *, interval_sec: float = 5.0) -> None:
        self._ud = userdata
        self._interval = interval_sec
        self._task: asyncio.Task[None] | None = None
        self.coverage: float = 0.0

    def start(self) -> None:
        """Launch the watcher as a detached background task."""
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def aclose(self) -> None:
        """Stop the watcher (idempotent)."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    def _coverage(self) -> float:
        total = len(self._ud.ctx.plan.questions)
        if total == 0:
            return 1.0
        return min(self._ud.ctx.cursor, total) / total

    async def _run(self) -> None:
        try:
            while not state.is_complete(self._ud):
                self.coverage = self._coverage()
                log.info(
                    "director: coverage=%.0f%% (cursor=%d/%d, section=%s)",
                    self.coverage * 100,
                    self._ud.ctx.cursor,
                    len(self._ud.ctx.plan.questions),
                    state.current_section(self._ud),
                )
                await asyncio.sleep(self._interval)
            self.coverage = 1.0
            log.info("director: interview plan fully covered")
        except asyncio.CancelledError:  # pragma: no cover - cancellation path
            raise
        except Exception:  # noqa: BLE001 - a watcher must never crash the call
            log.exception("director: coverage watcher error (ignored)")
