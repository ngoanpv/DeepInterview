"""LiveKit Agents worker entrypoint for the DeepInterview live voice loop (WP-5).

REQUIRES the optional ``livekit`` extra and live keys to RUN:

    uv sync --extra livekit
    # plus LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET and an STT/TTS/LLM
    # provider + key (Deepgram / Cartesia / OpenAI / Gemini); falls back to the
    # most basic available component when a provider/key is missing.

    python -m deepinterview_agent.worker dev      # or: start / connect

This module imports ``livekit.agents`` at load time, so it is never imported by
the offline test path. It wires a precomputed ``InterviewContext`` (built by the
WP-6 prep pipeline) into a lean live :class:`Interviewer` session: heavy
reasoning already happened in prep; the turn path stays cheap. Persistence +
scoring are deferred to a shutdown callback so they never block a turn.
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
from .live.director import Director
from .live.interviewer import Interviewer
from .live.state import InterviewUserdata
from .shared_models import RoomMetadata, ScoreRequest

log = get_logger(__name__)


# --- component factories -----------------------------------------------------
# Each returns the configured provider plugin, or the most basic available
# fallback when the selected provider's key is missing (English-first defaults).


def build_stt(settings):  # noqa: ANN001, ANN201 - livekit plugin types optional
    provider = settings.stt_provider
    if provider == "deepgram" and settings.deepgram_api_key:
        from livekit.plugins import deepgram  # noqa: PLC0415

        return deepgram.STT(api_key=settings.deepgram_api_key, language="en")
    if provider == "soniox" and settings.soniox_api_key:
        from livekit.plugins import soniox  # noqa: PLC0415

        return soniox.STT(api_key=settings.soniox_api_key)
    log.warning("build_stt: no configured STT provider/key; using Deepgram default")
    from livekit.plugins import deepgram  # noqa: PLC0415

    return deepgram.STT()


def build_llm(settings):  # noqa: ANN001, ANN201
    provider = settings.llm_provider
    if provider == "openai" and settings.openai_api_key:
        from livekit.plugins import openai  # noqa: PLC0415

        return openai.LLM(model=settings.openai_model, api_key=settings.openai_api_key)
    if provider == "gemini" and settings.gemini_api_key:
        from livekit.plugins import google  # noqa: PLC0415

        # Live tier: lowest-latency flash on the real-time turn path.
        return google.LLM(model=settings.gemini_model_live, api_key=settings.gemini_api_key)
    log.warning("build_llm: no configured LLM provider/key; using OpenAI default")
    from livekit.plugins import openai  # noqa: PLC0415

    return openai.LLM()


def build_tts(settings):  # noqa: ANN001, ANN201
    provider = settings.tts_provider
    if provider == "cartesia" and settings.cartesia_api_key:
        from livekit.plugins import cartesia  # noqa: PLC0415

        return cartesia.TTS(api_key=settings.cartesia_api_key)
    if provider == "elevenlabs" and settings.elevenlabs_api_key:
        from livekit.plugins import elevenlabs  # noqa: PLC0415

        return elevenlabs.TTS(api_key=settings.elevenlabs_api_key)
    log.warning("build_tts: no configured TTS provider/key; using Cartesia default")
    from livekit.plugins import cartesia  # noqa: PLC0415

    return cartesia.TTS()


def build_vad():  # noqa: ANN201
    from livekit.plugins import silero  # noqa: PLC0415

    return silero.VAD.load()


# --- session id --------------------------------------------------------------


def _session_id_from_room(ctx: JobContext) -> str:
    """Derive the session id from room metadata JSON, falling back to room name."""
    metadata = getattr(ctx.room, "metadata", None)
    if metadata:
        try:
            return RoomMetadata.model_validate_json(metadata).session_id
        except Exception as exc:  # noqa: BLE001 - tolerate malformed metadata
            log.warning("worker: bad room metadata, using room name (%s)", exc)
    return ctx.room.name


# --- entrypoint --------------------------------------------------------------


async def entrypoint(ctx: JobContext) -> None:
    settings = get_settings()
    deps = build_deps(settings)

    await ctx.connect()
    session_id = _session_id_from_room(ctx)

    interview_ctx = await deps.repo.load_context(session_id)
    if interview_ctx is None:
        log.error("worker: no InterviewContext for session %s; aborting", session_id)
        return

    userdata = InterviewUserdata(ctx=interview_ctx, session_id=session_id)

    session: AgentSession[InterviewUserdata] = AgentSession(
        userdata=userdata,
        stt=build_stt(settings),
        llm=build_llm(settings),
        tts=build_tts(settings),
        vad=build_vad(),
        # Lean live loop: low-latency turns. Turn detection is on by default in
        # 1.x; preemptive generation starts the LLM before end-of-turn settles.
        preemptive_generation=True,
    )

    director = Director(userdata)
    director.start()

    async def _on_shutdown() -> None:
        await director.aclose()
        # Persist whatever was captured, best-effort, off the turn path.
        try:
            await deps.repo.save_transcript(session_id, userdata.transcript)
        except Exception:  # noqa: BLE001
            log.exception("worker: save_transcript failed for %s", session_id)
        # Fire scoring (WP-7) best-effort; never block shutdown on it.
        api_base = f"http://localhost:{settings.agent_api_port}"
        try:
            import httpx  # noqa: PLC0415

            req = ScoreRequest(session_id=session_id)
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(f"{api_base}/api/score", json=req.model_dump())
        except Exception:  # noqa: BLE001
            log.exception("worker: scoring trigger failed for %s", session_id)

    ctx.add_shutdown_callback(_on_shutdown)

    await session.start(
        agent=Interviewer(userdata),
        room=ctx.room,
    )


def main() -> None:
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))


if __name__ == "__main__":
    main()
