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
    JobProcess,
    WorkerOptions,
    cli,
    metrics,
)

from .core.config import get_settings
from .core.deps import build_deps
from .core.logging import get_logger
from .live import state
from .live.director import Director
from .live.guard import SessionGuard
from .live.interviewer import Interviewer
from .live.state import InterviewUserdata
from .shared_models import InterviewContext, RoomMetadata, ScoreRequest

log = get_logger(__name__)


def wire_transcript_capture(session, userdata: InterviewUserdata) -> None:  # noqa: ANN001
    """Capture every committed conversation turn into the flat transcript log.

    ``conversation_item_added`` fires for both the candidate's real STT
    transcript and the agent's actually-spoken replies, so the persisted
    transcript reflects what was said — it no longer depends on the LLM
    remembering to call ``save_answer``, and an abrupt disconnect keeps every
    turn committed so far. (Answers for SCORING still come from ``save_answer``
    -> ``ctx.answers``; this log is the verbatim record.)
    """

    @session.on("conversation_item_added")
    def _on_item(ev) -> None:  # noqa: ANN001
        item = ev.item
        role = getattr(item, "role", None)
        text = getattr(item, "text_content", None)
        if role in ("user", "assistant") and text:
            state.add_turn(userdata, role, text)


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


def build_vad(proc: JobProcess | None = None):  # noqa: ANN201
    """Return the Silero VAD, preferring the prewarmed per-process instance."""
    if proc is not None and "vad" in proc.userdata:
        return proc.userdata["vad"]
    from livekit.plugins import silero  # noqa: PLC0415

    return silero.VAD.load()


def prewarm(proc: JobProcess) -> None:
    """Load the VAD model once per job process (LiveKit prewarm best practice).

    Loading Silero inside the entrypoint adds model-load latency to every job
    and blocks the event loop; ``prewarm_fnc`` runs before jobs are assigned.
    """
    from livekit.plugins import silero  # noqa: PLC0415

    proc.userdata["vad"] = silero.VAD.load()


# --- session id --------------------------------------------------------------


def _api_base(settings) -> str:  # noqa: ANN001
    """Base URL for the prep/score API: AGENT_API_URL, else same-host default."""
    return (settings.agent_api_url or f"http://localhost:{settings.agent_api_port}").rstrip("/")


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

    url = f"{_api_base(settings)}/api/session/{session_id}"
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
        vad=build_vad(ctx.proc),
        # Lean live loop: low-latency turns. Turn detection is on by default in
        # 1.x; preemptive generation starts the LLM before end-of-turn settles.
        preemptive_generation=True,
    )

    # Persisted transcript = real committed turns (STT + agent speech), not
    # whatever the LLM chose to pass to save_answer.
    wire_transcript_capture(session, userdata)

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

    # Cost discipline (Golden Rule #5): collect per-session STT/LLM/TTS usage so
    # voice cost is observable, and log the summary at shutdown.
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics(ev) -> None:  # noqa: ANN001
        usage_collector.collect(ev.metrics)

    api_base = _api_base(settings)

    async def _persist_via_api(has_answers: bool) -> bool:
        """Persist the live result through the API process.

        The worker runs in a SEPARATE process: with no Supabase configured the
        API's in-memory repo is the canonical store, so writing through our own
        ``deps.repo`` would land in a repo nobody reads (answers lost, never
        scored). POST the result to the API instead; direct repo writes below
        are the fallback for shared-store (Supabase) deployments.
        """
        import httpx  # noqa: PLC0415

        payload = {
            "context": userdata.ctx.model_dump(),
            "transcript": userdata.transcript,
            "status": None if has_answers else "no_answers",
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    f"{api_base}/api/session/{session_id}/live-result", json=payload
                )
            return resp.status_code == 200
        except Exception:  # noqa: BLE001
            log.exception("worker: live-result POST failed for %s", session_id)
            return False

    async def _persist_via_repo(has_answers: bool) -> bool:
        """Direct-store fallback (correct when both processes share Supabase)."""
        try:
            await deps.repo.save_transcript(session_id, userdata.transcript)
        except Exception:  # noqa: BLE001
            log.exception("worker: save_transcript failed for %s", session_id)
        try:
            await deps.repo.save_context(session_id, userdata.ctx)
        except Exception:  # noqa: BLE001
            log.error(
                "worker: save_context FAILED for %s — answers not persisted; "
                "skipping scoring to avoid a blank scorecard",
                session_id,
                exc_info=True,
            )
            # Mark errored so the report shows an honest message, not zeros.
            try:
                await deps.repo.update_status(session_id, "error")
            except Exception:  # noqa: BLE001
                log.error("worker: update_status(error) failed for %s", session_id, exc_info=True)
            return False
        if not has_answers:
            try:
                await deps.repo.update_status(session_id, "no_answers")
            except Exception:  # noqa: BLE001
                log.error("worker: update_status(no_answers) failed for %s", session_id, exc_info=True)
        return True

    async def _on_shutdown() -> None:
        await guard.aclose()
        await director.aclose()

        try:
            summary = usage_collector.get_summary()
            log.info("worker: session %s usage: %s", session_id, summary)
        except Exception:  # noqa: BLE001
            log.exception("worker: usage summary failed for %s", session_id)

        # An answer only counts if it has a non-empty transcript — a bare
        # save_answer("") must not flip the session into the scoring path.
        has_answers = any((a.transcript or "").strip() for a in userdata.ctx.answers)

        # Persist BEFORE scoring; if nothing persisted, do NOT score (run_score
        # would read the prep-time answer-less context -> blank card).
        persisted = await _persist_via_api(has_answers)
        if not persisted:
            persisted = await _persist_via_repo(has_answers)
        if not persisted or not has_answers:
            if not has_answers:
                log.info("worker: session %s has no answers; skipping scoring", session_id)
            return

        # Fire scoring (WP-7) best-effort; never block shutdown on it. The score
        # endpoint runs the full LLM pipeline inline, so allow it minutes (a 10s
        # ceiling would abandon nearly every real scoring run).
        try:
            import httpx  # noqa: PLC0415

            req = ScoreRequest(session_id=session_id)
            score_timeout = httpx.Timeout(10.0, read=600.0)
            async with httpx.AsyncClient(timeout=score_timeout) as client:
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
            prewarm_fnc=prewarm,
            ws_url=settings.livekit_url,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
        )
    )


if __name__ == "__main__":
    main()
