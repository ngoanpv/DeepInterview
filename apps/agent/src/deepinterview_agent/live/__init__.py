"""WP-5 live voice interviewer package.

Only :mod:`deepinterview_agent.live.state` is imported here: it is pure logic and
has NO dependency on ``livekit-agents`` (an optional extra). The livekit-coupled
modules (``interviewer``, ``handoffs``, ``director``) import ``livekit.agents`` at
module load and are therefore imported lazily by the worker, never from here — so
``import deepinterview_agent.live`` / ``...live.state`` succeeds with the extra
absent (and offline tests can exercise the state machine).
"""

from __future__ import annotations

from . import state

__all__ = ["state"]
