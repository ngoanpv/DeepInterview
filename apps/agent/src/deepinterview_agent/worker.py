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
from .live.guard import SessionGuard
from .live.interviewer import Interviewer
from .live.state import InterviewUserdata
from .shared_models import InterviewContext, RoomMetadata, ScoreRequest

log = get_logger(__name__)


# --- component factories -----------------------------------------------------
# Each returns the configured provider plugin, or the most basic available
# fallback when the selected provider's key is missing (English-first defaults).


# Map our primary-language code onto the speech providers so STT transcribes —
# and TTS speaks — in the candidate's language, not just English. Deepgram
# nova-3 and Cartesia sonic-3 are multilingual; codes default to English when a
# language isn't mapped. `mixed` (code-switching) uses Deepgram's "multi" model.
_STT_LANG = {"en": "en", "vi": "vi", "es": "es", "zh": "zh", "fr": "fr", "de": "de", "ja": "ja"}
_TTS_LANG = {"en": "en", "vi": "vi", "es": "es", "zh": "zh", "fr": "fr", "de": "de", "ja": "ja"}


def _stt_lang(language: str, mixed: bool) -> str:
    return "multi" if mixed else _STT_LANG.get(language, "en")


def build_stt(settings, language="en", mixed=False):  # noqa: ANN001, ANN201 - livekit plugin types optional
    lang = _stt_lang(language, mixed)
    # Deepgram now lists Vietnamese on nova-3 (lower WER than nova-2), so we use
    # nova-3 for all languages. If a non-English language returns NO transcripts
    # in streaming (nova-3 vi may be batch-only), revert the non-en branch to:
    #     model = "nova-3" if lang in ("en", "multi") else "nova-2"
    model = "nova-3"
    provider = settings.stt_provider
    if provider == "deepgram" and settings.deepgram_api_key:
        from livekit.plugins import deepgram  # noqa: PLC0415

        return deepgram.STT(api_key=settings.deepgram_api_key, language=lang, model=model)
    if provider == "soniox" and settings.soniox_api_key:
        from livekit.plugins import soniox  # noqa: PLC0415

        return soniox.STT(api_key=settings.soniox_api_key)
    log.warning("build_stt: no configured STT provider/key; using Deepgram default")
    from livekit.plugins import deepgram  # noqa: PLC0415

    return deepgram.STT(language=lang, model=model)


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


# Languages Cartesia sonic speaks. Notably EXCLUDES Vietnamese — anything not in
# this set is routed to ElevenLabs Flash v2.5 (low-latency, speaks vi) when an
# ElevenLabs key is set, else to Gemini native TTS as a slower last resort.
_CARTESIA_LANGS = {"en", "es", "fr", "de", "ja", "zh", "pt", "hi", "it", "ko", "nl", "pl", "ru", "sv", "tr"}


def build_tts(settings, language="en"):  # noqa: ANN001, ANN201
    lang = _TTS_LANG.get(language, "en")
    provider = settings.tts_provider
    needs_non_cartesia = language not in _CARTESIA_LANGS

    # ElevenLabs Flash v2.5 (~75ms, 32 languages incl. vi) is the low-latency
    # multilingual voice: it wins when explicitly selected, and it's the preferred
    # voice for any language Cartesia can't speak (e.g. Vietnamese) — replacing the
    # much slower Gemini native TTS, which now only serves as the vi fallback when
    # no ElevenLabs key is configured.
    if (provider == "elevenlabs" or needs_non_cartesia) and settings.elevenlabs_api_key:
        from livekit.plugins import elevenlabs  # noqa: PLC0415

        # "Sarah" is a free-tier-allowed default voice; the shared voice library
        # 402s on free plans. Flash v2.5 supports per-request language enforcement
        # — pass the ISO code so Vietnamese is pronounced as vi, not guessed.
        return elevenlabs.TTS(
            api_key=settings.elevenlabs_api_key,
            model=settings.elevenlabs_model,
            voice_id="EXAVITQu4vr4xnSDxMaL",
            language=lang,
        )

    # No ElevenLabs key but the language is outside Cartesia's set (e.g. vi): fall
    # back to Gemini native TTS so it is spoken correctly, just slower.
    if needs_non_cartesia and provider != "elevenlabs" and settings.gemini_api_key:
        from livekit.plugins.google.beta import GeminiTTS  # noqa: PLC0415

        log.info("build_tts: %r unsupported by Cartesia; using Gemini TTS fallback", language)
        return GeminiTTS(model=settings.gemini_tts_model, api_key=settings.gemini_api_key)

    if provider == "cartesia" and settings.cartesia_api_key:
        from livekit.plugins import cartesia  # noqa: PLC0415

        return cartesia.TTS(api_key=settings.cartesia_api_key, language=lang)
    log.warning("build_tts: no configured TTS provider/key; using Cartesia default")
    from livekit.plugins import cartesia  # noqa: PLC0415

    return cartesia.TTS(language=lang)


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


async def _load_context_via_api(session_id: str, settings) -> InterviewContext | None:  # noqa: ANN001
    """Fetch the prepped InterviewContext from the prep API over HTTP.

    The worker runs in a SEPARATE process from the API (``cli.run_app`` spawns its
    own job process), so the in-memory repo is not shared. Read the context from
    the API's ``GET /api/session/{id}`` SessionView instead. (With Supabase
    configured both processes share the store and either path works.)
    """
    import httpx  # noqa: PLC0415

    url = f"http://localhost:{settings.agent_api_port}/api/session/{session_id}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
    except Exception:  # noqa: BLE001
        log.exception("worker: failed to reach %s", url)
        return None
    if resp.status_code != 200:
        log.error("worker: GET %s -> %s", url, resp.status_code)
        return None
    ctx_data = resp.json().get("context")
    if not ctx_data:
        log.error("worker: session %s has no ready context", session_id)
        return None
    return InterviewContext.model_validate(ctx_data)


# --- entrypoint --------------------------------------------------------------


async def entrypoint(ctx: JobContext) -> None:
    settings = get_settings()
    deps = build_deps(settings)

    await ctx.connect()
    session_id = _session_id_from_room(ctx)

    interview_ctx = await _load_context_via_api(session_id, settings)
    if interview_ctx is None:
        log.error("worker: no InterviewContext for session %s; aborting", session_id)
        return

    userdata = InterviewUserdata(ctx=interview_ctx, session_id=session_id)

    # Route STT/TTS by the interview's primary language so a non-English session
    # (e.g. Vietnamese) is both understood and spoken — not just prompted for.
    lang_mode = interview_ctx.plan.language_mode
    session: AgentSession[InterviewUserdata] = AgentSession(
        userdata=userdata,
        stt=build_stt(settings, lang_mode.primary, lang_mode.mixed),
        llm=build_llm(settings),
        tts=build_tts(settings, lang_mode.primary),
        vad=build_vad(),
        # Lean live loop: low-latency turns. Turn detection is on by default in
        # 1.x; preemptive generation starts the LLM before end-of-turn settles.
        preemptive_generation=True,
    )

    director = Director(
        userdata, enable_adaptive=settings.enable_adaptive_difficulty
    )
    director.start()

    # Hard in-room cost/duration backstop (Golden Rule #5): ends the session if
    # it runs past the configured ceilings, independent of the web-layer cap on
    # interview creation. Started after the session is live (see below).
    guard = SessionGuard(
        session,
        userdata,
        max_duration_sec=settings.max_interview_duration_sec,
        max_turns=settings.max_interview_turns,
    )

    async def _on_shutdown() -> None:
        await guard.aclose()
        await director.aclose()
        # Persist whatever was captured, best-effort, off the turn path.
        try:
            await deps.repo.save_transcript(session_id, userdata.transcript)
        except Exception:  # noqa: BLE001
            log.exception("worker: save_transcript failed for %s", session_id)
        # The live loop only mutates the IN-MEMORY userdata.ctx (an AnswerRecord
        # is appended per answered turn — see live/state.py). Persist it BEFORE
        # scoring; if persistence FAILS we must NOT score, or run_score ->
        # load_context reads the prep-time (answer-less) context and produces a
        # blank "complete" scorecard (coverage 0%). Both processes share the
        # Supabase store (the in-memory repo is process-local; same caveat as the
        # load path).
        context_saved = False
        try:
            await deps.repo.save_context(session_id, userdata.ctx)
            context_saved = True
        except Exception:  # noqa: BLE001
            log.error(
                "worker: save_context FAILED for %s — answers not persisted; "
                "skipping scoring to avoid a blank scorecard",
                session_id,
                exc_info=True,
            )

        if not context_saved:
            # Persistence failed: mark the session errored so the report shows an
            # honest message rather than a misleading all-zeros card.
            try:
                await deps.repo.update_status(session_id, "error")
            except Exception:  # noqa: BLE001
                log.error("worker: update_status(error) failed for %s", session_id, exc_info=True)
            return

        if not userdata.ctx.answers:
            # Interview produced no answers — record an honest terminal state and
            # skip scoring entirely (no LLM calls, no blank "complete" card).
            log.info("worker: session %s has no answers; marking no_answers (skip scoring)", session_id)
            try:
                await deps.repo.update_status(session_id, "no_answers")
            except Exception:  # noqa: BLE001
                log.error("worker: update_status(no_answers) failed for %s", session_id, exc_info=True)
            return

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

    # Start the guard only once the session is live (it calls session.say /
    # session.shutdown); it runs detached until a ceiling trips or shutdown.
    guard.start()


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
