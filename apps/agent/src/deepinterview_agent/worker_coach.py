"""LiveKit Agents worker entrypoint for the spoken Study Coach (voice sub-phase).

REQUIRES the optional ``livekit`` extra and live keys to RUN:

    uv sync --extra livekit
    # plus LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET and an STT/TTS/LLM
    # provider + key (Deepgram / Cartesia / OpenAI / Gemini); falls back to the
    # most basic available component when a provider/key is missing.

    python -m deepinterview_agent.worker_coach dev   # or: start / connect

This is the SPOKEN counterpart to ``worker.py``: instead of running the
interview, it runs a post-interview coaching conversation. It imports
``livekit.agents`` at load time, so it is NEVER imported by the offline test
path. It REUSES ``worker.py``'s component factories and context-loading helpers
verbatim (no duplicated provider wiring), loads the precomputed
``InterviewContext`` (which carries the ``ScoreCard`` once scoring has run), and
starts a lean :class:`~deepinterview_agent.live.coach_agent.CoachAgent` session.

The heavy planning (``run_coach_plan`` / ``run_coach_chat``) stays OFFLINE in the
``coach/`` module and over the ``/api/coach`` routes; this worker only carries the
spoken turn loop and wires no retrieval tool onto it — grounded coaching lives in
the latency-tolerant ``/api/coach/chat`` route, not the live loop.

This module is integration-tested MANUALLY (it needs the livekit extra + live
keys); there is no offline unit test for the worker itself. The livekit-free
logic it relies on (instructions + weak-areas summary) IS unit-tested in
``tests/test_voice_coach.py``.
"""

from __future__ import annotations

from livekit.agents import (
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
)

from .core.config import get_settings
from .core.deps import build_deps
from .core.logging import get_logger
from .live.coach_agent import CoachAgent
from .live.state import InterviewUserdata, weak_areas_summary

# Reuse the interview worker's provider factories + context loaders verbatim so
# the coach worker and interview worker stay in lockstep (single source of truth).
from .worker import (
    _load_context_via_api,
    _session_id_from_room,
    build_llm,
    build_stt,
    build_tts,
    build_vad,
)

log = get_logger(__name__)


async def entrypoint(ctx: JobContext) -> None:
    settings = get_settings()
    deps = build_deps(settings)

    await ctx.connect()
    session_id = _session_id_from_room(ctx)

    interview_ctx = await _load_context_via_api(session_id, settings)
    if interview_ctx is None:
        log.error("worker_coach: no InterviewContext for session %s; aborting", session_id)
        return

    primary = interview_ctx.plan.language_mode.primary
    summary = weak_areas_summary(interview_ctx.scorecard)

    # Carry the same per-session userdata shape as the interview worker so the
    # transcript can be persisted on shutdown the same way.
    userdata = InterviewUserdata(ctx=interview_ctx, session_id=session_id)

    session: AgentSession[InterviewUserdata] = AgentSession(
        userdata=userdata,
        stt=build_stt(settings),
        llm=build_llm(settings),
        tts=build_tts(settings),
        vad=build_vad(),
        preemptive_generation=True,
    )

    async def _on_shutdown() -> None:
        try:
            await deps.repo.save_transcript(session_id, userdata.transcript)
        except Exception:  # noqa: BLE001
            log.exception("worker_coach: save_transcript failed for %s", session_id)

    ctx.add_shutdown_callback(_on_shutdown)

    await session.start(
        agent=CoachAgent(
            weak_areas_summary=summary,
            lang=primary,
        ),
        room=ctx.room,
    )


def main() -> None:
    # livekit-agents reads LIVEKIT_URL/API_KEY/API_SECRET from os.environ; we keep
    # them in Settings (.env), so pass them through explicitly to WorkerOptions.
    settings = get_settings()
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            ws_url=settings.livekit_url,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
        )
    )


if __name__ == "__main__":
    main()
