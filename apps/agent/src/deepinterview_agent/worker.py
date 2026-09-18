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
from .core.observability import init_observability
from .core.tracing import add_event, start_trace
from .live import state
from .live.director import Director
from .live.flusher import TranscriptFlusher
from .live.guard import SessionGuard
from .live.guard import wrap_up_line as guard_wrap_up_line
from .live.interviewer import Interviewer
from .live.state import InterviewUserdata
from .shared_models import InterviewContext, RoomMetadata, ScoreRequest

log = get_logger(__name__)


def wire_audio_path_logging(ctx: JobContext, session) -> None:
    """INFO-level tracing of the candidate→agent audio path.

    The default SDK logs are silent about track publish/subscribe and user
    speech state, which made a "the agent never hears the candidate" failure
    undiagnosable from logs. One line per lifecycle event, low volume.
    """

    def _kind(pub) -> str:
        return str(getattr(pub, "kind", "?"))

    @ctx.room.on("participant_connected")
    def _on_participant(p) -> None:
        log.info("audio-path: participant connected identity=%s", p.identity)

    @ctx.room.on("track_published")
    def _on_published(pub, p) -> None:
        log.info("audio-path: track PUBLISHED kind=%s muted=%s by %s",
                 _kind(pub), getattr(pub, "muted", "?"), p.identity)

    @ctx.room.on("track_subscribed")
    def _on_subscribed(track, pub, p) -> None:
        log.info("audio-path: track SUBSCRIBED kind=%s from %s", _kind(pub), p.identity)

    @ctx.room.on("track_muted")
    def _on_muted(p, pub) -> None:
        log.info("audio-path: track MUTED kind=%s by %s", _kind(pub), p.identity)

    @ctx.room.on("track_unmuted")
    def _on_unmuted(p, pub) -> None:
        log.info("audio-path: track UNMUTED kind=%s by %s", _kind(pub), p.identity)

    for p in ctx.room.remote_participants.values():
        pubs = {sid: _kind(pub) for sid, pub in p.track_publications.items()}
        log.info("audio-path: already present identity=%s tracks=%s", p.identity, pubs)

    @session.on("user_state_changed")
    def _on_user_state(ev) -> None:
        log.info("audio-path: user state -> %s", getattr(ev, "new_state", ev))

    @session.on("user_input_transcribed")
    def _on_user_transcribed(ev) -> None:
        log.info("audio-path: user transcript final=%s len=%d",
                 getattr(ev, "is_final", "?"), len(getattr(ev, "transcript", "") or ""))


def wire_transcript_capture(
    session, userdata: InterviewUserdata, *, tag_questions: bool = True
) -> None:
    """Capture every committed conversation turn into the flat transcript log.

    ``conversation_item_added`` fires for both the candidate's real STT
    transcript and the agent's actually-spoken replies, so the persisted
    transcript reflects what was said — it no longer depends on the LLM
    remembering to call ``save_answer``, and an abrupt disconnect keeps every
    turn committed so far. Answers for scoring come from ``save_answer`` ->
    ``ctx.answers``, with ``state.reconstruct_answers`` recovering any unsaved
    ones from this log at shutdown.

    ``tag_questions=False`` skips the per-turn question-id tag for sessions
    that reuse an interview context but are not answering its plan (the study
    coach) — otherwise coach chat would carry stale interview question ids.
    """

    @session.on("conversation_item_added")
    def _on_item(ev) -> None:
        item = ev.item
        role = getattr(item, "role", None)
        text = getattr(item, "text_content", None)
        if role in ("user", "assistant") and text:
            # Land every committed turn in the live trace too (role + size only,
            # never the verbatim text), so `deepinterview traces show` replays
            # the interview's shape. No-op when tracing is disabled or when no
            # live trace is open (e.g. the study-coach session).
            add_event("turn", {"role": role, "chars": len(text)})
            if tag_questions:
                state.add_turn(userdata, role, text)
            else:
                userdata.transcript.append({"role": role, "text": text})


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


def _deepgram_stt(lang: str, model: str, api_key=None):
    """Return a configured deepgram.STT instance with tuned params for each language tier.

    nova-3 (en/multi):
      - endpointing_ms=25: aggressive VAD is fine; semantic EOU model handles turns.
      - numerals=True: gated to this tier to keep the nova-2 flag set minimal —
        bad flag combos on non-English streams fail SILENTLY with zero
        transcripts (see the nova-3+vi note in build_stt), and smart_format
        already covers number formatting where supported.
      - keyterm: not set here (per-session domain terms could be injected later).

    nova-2 (all other languages incl. vi):
      - endpointing_ms=300: Deepgram's own server-side silence window; 25ms fires
        too eagerly for languages with more within-utterance pauses (e.g. Vietnamese),
        flooding us with fragmented partials before our LiveKit 1.2s window acts.

    smart_format=True applies to BOTH tiers (broadly language-supported:
    number/date formatting).
    """
    from livekit.plugins import deepgram

    is_nova3 = model == "nova-3"
    kwargs = dict(  # noqa: C408 - kwargs dict is mutated/expanded below; dict() reads better here
        language=lang,
        model=model,
        punctuate=True,
        filler_words=True,
        vad_events=True,
        numerals=is_nova3,
        smart_format=True,
        endpointing_ms=25 if is_nova3 else 300,
    )
    if api_key is not None:
        kwargs["api_key"] = api_key
    return deepgram.STT(**kwargs)


def _local_whisper_stt(settings, language: str, mixed: bool, vad=None):
    """Local Whisper (any OpenAI-compatible ``/v1/audio/transcriptions`` server).

    The openai plugin's STT is a BATCH client: its capabilities are
    ``streaming=use_realtime``, and ``use_realtime=True`` speaks OpenAI's
    proprietary Realtime WebSocket, which local Whisper servers don't implement.
    So it is wrapped in the SDK's ``StreamAdapter``, which uses the (already
    prewarmed) Silero VAD to cut the mic stream into utterances and calls the
    batch endpoint per utterance, re-exposing ``streaming=True``.

    The trade-off is real and documented: **no interim results** on this path —
    captions land per utterance instead of word by word. The semantic
    end-of-turn model reads final transcripts, so turn-taking still works.

    Code-switching does NOT go through ``_stt_lang`` here. That helper returns
    the string ``"multi"``, which is a *Deepgram model name*; Whisper rejects it
    and every transcript comes back empty — the same silent-no-transcripts class
    of failure as the nova-3+vi bug above. Whisper's own mechanism is
    ``detect_language``, which blanks the language and lets it auto-detect.
    """
    from livekit.agents import stt as agents_stt
    from livekit.plugins import openai

    return agents_stt.StreamAdapter(
        stt=openai.STT(
            model=settings.whisper_model,
            language=_STT_LANG.get(language, "en"),
            detect_language=mixed,
            base_url=settings.whisper_base_url,
            # Local servers want no auth, but the plugin rejects an empty key.
            api_key=settings.local_api_key,
        ),
        vad=vad or build_vad(),
    )


def build_stt(settings, language="en", mixed=False, vad=None):
    lang = _stt_lang(language, mixed)
    # Local path: no key, a base URL instead. Checked before the cloud branches
    # so an explicit local selection is never overridden.
    if _provider(settings, "stt") in _LOCAL_STT:
        return _local_whisper_stt(settings, language, mixed, vad=vad)
    # CONFIRMED in live testing (2026-06-10): nova-3 + language=vi returns NO
    # transcripts on Deepgram's streaming API (English worked end-to-end in the
    # same build) — the exact failure this comment predicted. Non-English
    # languages therefore route to nova-2, which supports them in streaming;
    # nova-3 stays for en/multi where it has the lower WER.
    model = "nova-3" if lang in ("en", "multi") else "nova-2"
    provider = _provider(settings, "stt")
    if provider == "deepgram" and settings.deepgram_api_key:
        return _deepgram_stt(lang, model, api_key=settings.deepgram_api_key)
    if provider == "soniox" and settings.soniox_api_key:
        from livekit.plugins import soniox

        return soniox.STT(api_key=settings.soniox_api_key)
    log.warning("build_stt: no configured STT provider/key; using Deepgram default")
    return _deepgram_stt(lang, model)


def _require_live_providers(settings) -> None:
    """Fail fast when a selected real live provider is missing its credential.

    The live loop cannot recover from a missing/typo'd key mid-call — the
    candidate joins, then the first turn errors (or the whole session runs on a
    keyless default). Catch it before the session starts. Mock/unset providers
    are left alone (the offline path); only *selected real* providers are
    checked, so this raises solely on genuine misconfiguration.
    """
    missing: list[str] = []
    llm = (settings.llm_provider or "").lower()
    if llm == "gemini" and not settings.gemini_api_key:
        missing.append("GEMINI_API_KEY (LLM_PROVIDER=gemini)")
    elif llm == "openai" and not settings.openai_api_key:
        missing.append("OPENAI_API_KEY (LLM_PROVIDER=openai)")
    stt = (settings.stt_provider or "").lower()
    if stt == "deepgram" and not settings.deepgram_api_key:
        missing.append("DEEPGRAM_API_KEY (STT_PROVIDER=deepgram)")
    elif stt == "soniox" and not settings.soniox_api_key:
        missing.append("SONIOX_API_KEY (STT_PROVIDER=soniox)")
    tts = (settings.tts_provider or "").lower()
    if tts == "cartesia" and not settings.cartesia_api_key:
        missing.append("CARTESIA_API_KEY (TTS_PROVIDER=cartesia)")
    elif tts == "elevenlabs" and not settings.elevenlabs_api_key:
        missing.append("ELEVENLABS_API_KEY (TTS_PROVIDER=elevenlabs)")
    missing.extend(_unreachable_local_providers(settings))
    if missing:
        raise RuntimeError(
            "Live interview cannot start — missing provider credentials: "
            + "; ".join(missing)
        )


# Accepted values per stage for the local path. These name a *contract* — "an
# OpenAI-compatible server at a base URL" — not a vendor, so each stage takes
# aliases: whatever you actually run, the adapter is identical. Whisper and
# Qwen3-ASR both serve /v1/audio/transcriptions; Ollama, vLLM, LM Studio and
# llama.cpp all serve /v1/chat/completions; Kokoro serves /v1/audio/speech.
# `local` works everywhere as the neutral name.
_LOCAL_LLM = frozenset({"ollama", "vllm", "llamacpp", "lmstudio", "local"})
_LOCAL_STT = frozenset({"whisper", "faster-whisper", "qwen3-asr", "qwen-asr", "speaches", "local"})
_LOCAL_TTS = frozenset({"kokoro", "local"})

# Selected local provider -> (base-URL setting, env var named in the error).
_LOCAL_PROVIDERS = {
    "llm_provider": (_LOCAL_LLM, "ollama_base_url", "OLLAMA_BASE_URL"),
    "stt_provider": (_LOCAL_STT, "whisper_base_url", "WHISPER_BASE_URL"),
    "tts_provider": (_LOCAL_TTS, "kokoro_base_url", "KOKORO_BASE_URL"),
}


def _provider(settings, stage: str) -> str:
    """Normalized provider value for a stage.

    Case matters more than it looks: the builders compared the raw string while
    preflight lowercased it, so ``STT_PROVIDER=Whisper`` passed the credential
    check and then fell through to the *Deepgram* default — a cloud call on the
    "no cloud keys" path. One normalizer, used by both.
    """
    return (getattr(settings, f"{stage}_provider", "") or "").strip().lower()


def _unreachable_local_providers(settings) -> list[str]:
    """Local providers have no credential — an unreachable server is the failure.

    A missing API key is caught above; the local path's equivalent is "the model
    server isn't running", which otherwise surfaces only once the candidate has
    joined and the first turn errors. One bounded GET per selected local
    provider, before the greeting, turns that into a startup error naming the
    URL and the env var. Never on the turn path.
    """
    import httpx

    problems: list[str] = []
    for field, (accepted, url_field, env_name) in _LOCAL_PROVIDERS.items():
        stage = field.removesuffix("_provider")
        selected = _provider(settings, stage)
        if selected not in accepted:
            continue
        base = (getattr(settings, url_field, "") or "").rstrip("/")
        if not base:
            problems.append(f"{env_name} ({field.upper()}={selected})")
            continue
        try:
            httpx.get(f"{base}/models", timeout=settings.local_probe_timeout_sec)
        except Exception as exc:  # noqa: BLE001 - any failure to reach it is fatal
            # A 4xx/5xx still proves something is listening; only transport
            # failures (refused/DNS/timeout) mean "server isn't there".
            problems.append(f"{env_name}={base} unreachable ({type(exc).__name__}: {exc})")
    return problems


def build_llm(settings):
    provider = _provider(settings, "llm")
    if provider in _LOCAL_LLM:
        from livekit.plugins import openai

        # Local LLM on the turn path via Ollama's OpenAI-compatible endpoint.
        # Live tier when set (see Settings.ollama_model_live): the prep model is
        # sized for a pipeline nobody is waiting on, the turn loop is not.
        # Falling back to ollama_model keeps the un-tuned path byte-identical.
        model = settings.ollama_model_live or settings.ollama_model
        if settings.ollama_model_live:
            log.info(
                "build_llm: local live tier — turn path on %r (prep/scoring stays on %r)",
                settings.ollama_model_live,
                settings.ollama_model,
            )
        return openai.LLM(
            model=model,
            base_url=settings.ollama_base_url,
            api_key=settings.local_api_key,
        )
    if provider == "openai" and settings.openai_api_key:
        from livekit.plugins import openai

        return openai.LLM(model=settings.openai_model, api_key=settings.openai_api_key)
    if provider == "gemini" and settings.gemini_api_key:
        from livekit.plugins import google

        # Live tier: lowest-latency flash on the real-time turn path.
        return google.LLM(model=settings.gemini_model_live, api_key=settings.gemini_api_key)
    log.warning("build_llm: no configured LLM provider/key; using OpenAI default")
    from livekit.plugins import openai

    return openai.LLM()


# Languages Cartesia sonic speaks. Notably EXCLUDES Vietnamese — anything not in
# this set is routed to ElevenLabs Flash v2.5 (low-latency, speaks vi) when an
# ElevenLabs key is set, else to Gemini native TTS as a slower last resort.
_CARTESIA_LANGS = {"en", "es", "fr", "de", "ja", "zh", "pt", "hi", "it", "ko", "nl", "pl", "ru", "sv", "tr"}


# Kokoro-82M encodes the language in the voice id's prefix, so picking a voice
# IS picking a language: leaving the English default on a Japanese session would
# read Japanese text with an American accent. Notably absent: Vietnamese —
# Kokoro has no vi voice, so vi sessions fall through to the cloud chain.
_KOKORO_VOICE = {
    "en": "af_heart",
    "ja": "jf_alpha",
    "zh": "zf_xiaobei",
    "es": "ef_dora",
    "fr": "ff_siwis",
    "hi": "hf_alpha",
    "it": "if_sara",
    "pt": "pf_dora",
}


def _local_kokoro_tts(settings, language="en"):
    """Local Kokoro (kokoro-fastapi's OpenAI-compatible ``/v1/audio/speech``).

    Wrapped in the SDK's TTS ``StreamAdapter`` because the openai plugin's TTS
    declares ``streaming=False``: unwrapped, the agent would synthesize a whole
    answer before speaking a word. The adapter's sentence tokenizer feeds it one
    sentence at a time as the LLM streams, so speech starts after the first
    sentence — the same shape as the streaming cloud voices.
    """
    from livekit.agents import tts as agents_tts
    from livekit.plugins import openai
    from livekit.plugins.openai.tts import AUDIO_STREAM_MODELS

    # Guard the silent-failure mode: a model id outside AUDIO_STREAM_MODELS
    # sends synthesis down the plugin's SSE branch, which yields no audio and
    # raises nothing. Never let that happen quietly.
    model = settings.kokoro_model
    if model not in AUDIO_STREAM_MODELS:
        log.warning(
            "build_tts: KOKORO_MODEL=%r is outside %s, which would produce SILENT "
            "audio with no error; using 'tts-1' instead (kokoro-fastapi ignores "
            "the model name).",
            model,
            sorted(AUDIO_STREAM_MODELS),
        )
        model = "tts-1"

    # An explicit KOKORO_VOICE always wins; otherwise the voice is derived from
    # the session language so the accent matches the words.
    voice = settings.kokoro_voice or _KOKORO_VOICE.get(language, "af_heart")

    return agents_tts.StreamAdapter(
        tts=openai.TTS(
            model=model,
            voice=voice,
            base_url=settings.kokoro_base_url,
            api_key=settings.local_api_key,
            response_format=settings.kokoro_response_format,
        )
    )


def build_tts(settings, language="en"):
    lang = _TTS_LANG.get(language, "en")
    provider = _provider(settings, "tts")
    needs_non_cartesia = language not in _CARTESIA_LANGS

    # Local path first: an explicit local selection must never be silently
    # overridden by the cloud language-routing chain below. Kokoro can't speak
    # every language we support, so an unsupported one falls through to the
    # cloud voices rather than reading the text in the wrong language.
    if provider in _LOCAL_TTS:
        if language in _KOKORO_VOICE or settings.kokoro_voice:
            return _local_kokoro_tts(settings, language)
        log.warning(
            "build_tts: Kokoro has no voice for %r; falling back to a cloud voice. "
            "Set KOKORO_VOICE to force a specific one.",
            language,
        )

    # ElevenLabs Flash v2.5 (~75ms, 32 languages incl. vi) is the low-latency
    # multilingual voice: it wins when explicitly selected, and it's the preferred
    # voice for any language Cartesia can't speak (e.g. Vietnamese) — replacing the
    # much slower Gemini native TTS, which now only serves as the vi fallback when
    # no ElevenLabs key is configured.
    if (provider == "elevenlabs" or needs_non_cartesia) and settings.elevenlabs_api_key:
        from livekit.plugins import elevenlabs

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
        from livekit.plugins.google.beta import GeminiTTS

        log.info("build_tts: %r unsupported by Cartesia; using Gemini TTS fallback", language)
        return GeminiTTS(model=settings.gemini_tts_model, api_key=settings.gemini_api_key)

    if provider == "cartesia" and settings.cartesia_api_key:
        from livekit.plugins import cartesia

        return cartesia.TTS(api_key=settings.cartesia_api_key, language=lang)
    log.warning("build_tts: no configured TTS provider/key; using Cartesia default")
    from livekit.plugins import cartesia

    return cartesia.TTS(language=lang)


# Languages the LiveKit multilingual end-of-turn model can judge semantically.
# Vietnamese is NOT among them — for unsupported languages the session falls
# back to silence-based endpointing, where the default 0.5s cutoff chops
# natural mid-sentence pauses into separate turns (confirmed in vi testing:
# fragmented one-clause "answers" with the agent jumping in between).
_EOU_MODEL_LANGS = frozenset(
    {"en", "es", "fr", "de", "it", "pt", "nl", "zh", "ja", "ko", "id", "tr", "ru"}
)


def build_turn_handling(language: str = "en") -> dict:
    """Turn-handling config shared by the interview and coach sessions.

    Defenses on top of the SDK defaults:

    * ``min_words: 3`` — an interruption only registers once the candidate has
      actually SAID a few transcribed words. The default (0) lets raw VAD
      energy interrupt, so a door slam or background chatter cuts the
      interviewer off mid-sentence.
    * Semantic end-of-turn (``MultilingualModel``) for languages it supports —
      "is the candidate done?" is judged from the transcript instead of
      waiting for clean silence.
    * For languages the model can't judge (e.g. Vietnamese): stretch the
      silence endpointing window instead (1.2s min / 4s max) so natural
      pauses don't end the candidate's turn mid-sentence.
    """
    handling: dict = {"interruption": {"min_words": 3}}
    if language in _EOU_MODEL_LANGS:
        try:
            from livekit.plugins.turn_detector.multilingual import (
                MultilingualModel,
            )

            handling["turn_detection"] = MultilingualModel()
            return handling
        except Exception:  # noqa: BLE001 - optional model; fall through to endpointing
            log.warning("build_turn_handling: turn-detector unavailable; using endpointing")
    handling["endpointing"] = {"min_delay": 1.2, "max_delay": 4.0}
    return handling


def build_room_options(settings):
    """Room I/O options: BVC noise cancellation, strictly opt-in (ENABLE_BVC).

    BVC strips background noise BEFORE VAD/STT see it, but its native filter
    failed to initialize in the slim arm64 container and the input audio
    stream it was attached to delivered NO frames — the agent heard nothing
    for the whole session. So it is off unless ENABLE_BVC=true AND the
    deployment is LiveKit Cloud (BVC is a Cloud feature). Noise robustness
    otherwise comes from the semantic turn detector + min_words gate.
    Returns None (SDK defaults) when not enabled.
    """
    url = settings.livekit_url or ""
    if not settings.enable_bvc or "livekit.cloud" not in url:
        return None
    try:
        from livekit.agents.voice.room_io import AudioInputOptions, RoomOptions
        from livekit.plugins import noise_cancellation

        return RoomOptions(audio_input=AudioInputOptions(noise_cancellation=noise_cancellation.BVC()))
    except Exception:  # noqa: BLE001 - optional plugin; raw audio still works
        log.warning("build_room_options: noise-cancellation unavailable; using raw mic audio")
        return None


def build_conn_options(settings):
    """Widen the SDK's 10s per-request ceiling when a local model is selected.

    ``APIConnectOptions.timeout`` defaults to 10s — comfortable for a cloud
    model, but a local one that is cold, swapping, or sharing a GPU regularly
    needs longer just to emit its first token. At the default, every turn aborts
    before the model answers and the interview is silently dead.

    Returns ``None`` for the all-cloud path so its behaviour is bit-for-bit
    unchanged. ``max_retry=1`` because a local endpoint that is down stays down:
    three 30s retries would wedge the session for a minute and a half.
    """
    if not any(
        _provider(settings, stage) in accepted
        for stage, accepted in (("llm", _LOCAL_LLM), ("stt", _LOCAL_STT), ("tts", _LOCAL_TTS))
    ):
        return None

    from livekit.agents import APIConnectOptions
    from livekit.agents.voice.agent_session import SessionConnectOptions

    opts = APIConnectOptions(timeout=settings.local_provider_timeout_sec, max_retry=1)
    log.info(
        "build_conn_options: local provider selected; per-request timeout %.0fs",
        settings.local_provider_timeout_sec,
    )
    return SessionConnectOptions(
        stt_conn_options=opts, llm_conn_options=opts, tts_conn_options=opts
    )


def build_vad(proc: JobProcess | None = None):
    """Return the Silero VAD, preferring the prewarmed per-process instance."""
    if proc is not None and "vad" in proc.userdata:
        return proc.userdata["vad"]
    from livekit.plugins import silero

    return silero.VAD.load()


def prewarm(proc: JobProcess) -> None:
    """Load the VAD model once per job process (LiveKit prewarm best practice).

    Loading Silero inside the entrypoint adds model-load latency to every job
    and blocks the event loop; ``prewarm_fnc`` runs before jobs are assigned.
    """
    from livekit.plugins import silero

    proc.userdata["vad"] = silero.VAD.load()


# --- session id --------------------------------------------------------------


def _api_base(settings) -> str:
    """Base URL for the prep/score API: AGENT_API_URL, else same-host default."""
    return (settings.agent_api_url or f"http://localhost:{settings.agent_api_port}").rstrip("/")


def _internal_headers(settings) -> dict[str, str]:
    """Auth header for the agent API's guarded write endpoints when configured."""
    secret = getattr(settings, "internal_api_secret", None)
    return {"X-Internal-Secret": secret} if secret else {}


def _session_id_from_room(ctx: JobContext) -> str:
    """Derive the session id for this job.

    Resolution order (first hit wins):
      1. explicit-dispatch job metadata JSON ``{"session_id": ...}`` — what the
         web token's ``roomConfig.agents[0].metadata`` carries (issue #67 fix);
      2. room metadata JSON (legacy path);
      3. room name (the interview page pins room = session id).
    """
    job_metadata = getattr(getattr(ctx, "job", None), "metadata", None)
    if job_metadata:
        try:
            return RoomMetadata.model_validate_json(job_metadata).session_id
        except Exception as exc:  # noqa: BLE001 - tolerate malformed metadata
            log.warning("worker: bad job metadata, trying room metadata (%s)", exc)
    metadata = getattr(ctx.room, "metadata", None)
    if metadata:
        try:
            return RoomMetadata.model_validate_json(metadata).session_id
        except Exception as exc:  # noqa: BLE001 - tolerate malformed metadata
            log.warning("worker: bad room metadata, using room name (%s)", exc)
    return ctx.room.name


async def _load_context_via_api(session_id: str, settings) -> InterviewContext | None:
    """Fetch the prepped InterviewContext from the prep API over HTTP.

    The worker runs in a SEPARATE process from the API (``cli.run_app`` spawns its
    own job process), so the in-memory repo is not shared. Read the context from
    the API's ``GET /api/session/{id}`` SessionView instead. (With Supabase
    configured both processes share the store and either path works.)
    """
    import httpx

    url = f"{_api_base(settings)}/api/session/{session_id}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)  # GET read path is unguarded
    except Exception:
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


async def _load_context_with_retry(session_id: str, settings, *, timeout_sec: float = 60.0) -> InterviewContext | None:
    """Poll for the prepped context until prep finishes or the deadline hits.

    The interview page is joinable while prep is still running, so a candidate
    can enter the room seconds before the plan lands. A single fetch would see
    "no ready context" and abort — leaving the browser on "Connecting your
    interviewer…" with a healthy room and no agent (issue #67). Poll instead.
    """
    import asyncio

    import httpx

    deadline = asyncio.get_event_loop().time() + timeout_sec
    attempt = 0
    while True:
        attempt += 1
        try:
            ctx = await _load_context_via_api(session_id, settings)
        except (httpx.HTTPError, ValueError, KeyError):
            ctx = None
        if ctx is not None:
            if attempt > 1:
                log.info("worker: context for %s ready after %d attempts", session_id, attempt)
            return ctx
        if asyncio.get_event_loop().time() >= deadline:
            return None
        await asyncio.sleep(2.0)


# --- entrypoint --------------------------------------------------------------


async def entrypoint(ctx: JobContext) -> None:
    settings = get_settings()
    init_observability(settings)
    deps = build_deps(settings)

    # Fail fast on a misconfigured live provider before the candidate connects,
    # rather than mid-interview on the first turn.
    _require_live_providers(settings)

    await ctx.connect()
    session_id = _session_id_from_room(ctx)

    # The room is joinable while prep is still running — wait for the plan
    # instead of aborting on the first "not ready yet" (which strands the
    # candidate on "Connecting your interviewer…", issue #67).
    interview_ctx = await _load_context_with_retry(session_id, settings)
    if interview_ctx is None:
        log.error("worker: no InterviewContext for session %s; aborting", session_id)
        return

    userdata = InterviewUserdata(ctx=interview_ctx, session_id=session_id)

    # Route STT/TTS by the interview's primary language so a non-English session
    # (e.g. Vietnamese) is both understood and spoken — not just prompted for.
    lang_mode = interview_ctx.plan.language_mode

    # Trace the live session: turn events (wire_transcript_capture, below) land
    # here so `deepinterview traces show` / GET /api/traces/{id} replay the
    # interview's shape. The trace spans the whole job — opened here, closed in
    # the shutdown callback the SDK always runs at job end. No-op when disabled.
    _live_trace = start_trace(
        "live",
        session_id=session_id,
        metadata={
            "language": lang_mode.primary,
            "questions": len(interview_ctx.plan.questions),
        },
    )
    _live_trace.__enter__()
    add_event("live.start", {"questions": len(interview_ctx.plan.questions)})
    # Built once and shared: the local Whisper STT needs a VAD to segment the
    # mic stream, and loading Silero twice would waste the prewarm.
    vad = build_vad(ctx.proc)
    conn_options = build_conn_options(settings)
    session: AgentSession[InterviewUserdata] = AgentSession(
        userdata=userdata,
        stt=build_stt(settings, lang_mode.primary, lang_mode.mixed, vad=vad),
        llm=build_llm(settings),
        tts=build_tts(settings, lang_mode.primary),
        vad=vad,
        # Only set for local providers; None keeps the SDK defaults (see
        # build_conn_options), so the cloud path is untouched.
        **({"conn_options": conn_options} if conn_options else {}),
        # Lean live loop: preemptive generation is on by default in 1.5.x;
        # turn_handling adds the noisy-environment defenses (semantic
        # end-of-turn + word-gated interruptions — see build_turn_handling).
        turn_handling=build_turn_handling(lang_mode.primary),
    )

    # Persisted transcript = real committed turns (STT + agent speech), not
    # whatever the LLM chose to pass to save_answer.
    wire_transcript_capture(session, userdata)
    wire_audio_path_logging(ctx, session)

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
        wrap_up_line=guard_wrap_up_line(lang_mode.primary),
    )

    # Cost discipline (Golden Rule #5): collect per-session STT/LLM/TTS usage so
    # voice cost is observable, and log the summary at shutdown.
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics(ev) -> None:
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
        import httpx

        payload = {
            "context": userdata.ctx.model_dump(),
            "transcript": userdata.transcript,
            "status": None if has_answers else "no_answers",
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    f"{api_base}/api/session/{session_id}/live-result",
                    json=payload,
                    headers=_internal_headers(settings),
                )
            return resp.status_code == 200
        except Exception:
            log.exception("worker: live-result POST failed for %s", session_id)
            return False

    async def _flush_checkpoint(context, transcript: list[dict]) -> None:
        """Off-path partial persist for the TranscriptFlusher (non-terminal).

        Best-effort: any failure is swallowed by the flusher. Never marks the
        session terminal — a checkpoint is a mid-interview snapshot, and the
        live-result endpoint refuses writes once a session is terminal anyway.
        """
        import httpx

        payload = {
            "context": context.model_dump(),
            "transcript": transcript,
            "status": None,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{api_base}/api/session/{session_id}/live-result",
                json=payload,
                headers=_internal_headers(settings),
            )

    flusher = TranscriptFlusher(
        userdata,
        _flush_checkpoint,
        interval_sec=settings.transcript_flush_interval_sec,
    )

    async def _persist_via_repo(has_answers: bool) -> bool:
        """Direct-store fallback (correct when both processes share Supabase)."""
        try:
            await deps.repo.save_transcript(session_id, userdata.transcript)
        except Exception:
            log.exception("worker: save_transcript failed for %s", session_id)
        try:
            await deps.repo.save_context(session_id, userdata.ctx)
        except Exception:
            log.exception(
                "worker: save_context FAILED for %s — answers not persisted; "
                "skipping scoring to avoid a blank scorecard",
                session_id,
            )
            # Mark errored so the report shows an honest message, not zeros.
            try:
                await deps.repo.update_status(session_id, "error")
            except Exception:
                log.exception("worker: update_status(error) failed for %s", session_id)
            return False
        if not has_answers:
            try:
                await deps.repo.update_status(session_id, "no_answers")
            except Exception:
                log.exception("worker: update_status(no_answers) failed for %s", session_id)
        return True

    async def _on_shutdown() -> None:
        # Close the live trace first so the full session (turns + answers) is
        # queryable the moment the job drains.
        try:
            add_event(
                "live.end",
                {
                    "turns": len(userdata.transcript),
                    "answers": len(
                        [a for a in userdata.ctx.answers if (a.transcript or "").strip()]
                    ),
                },
            )
        finally:
            # Observability must never prevent the authoritative persist and
            # scoring trigger below. LiveKit executes shutdown callbacks in a
            # different asyncio Context from the entrypoint that opened this
            # trace; tracing handles that normally, and this boundary remains
            # a final guard against any optional tracing backend failure.
            try:
                _live_trace.__exit__(None, None, None)
            except Exception:
                log.exception("worker: live trace close failed for %s; continuing", session_id)

        # Stop the checkpointer first so it can't race the final, authoritative
        # persist below.
        await flusher.aclose()
        await guard.aclose()
        await director.aclose()

        try:
            summary = usage_collector.get_summary()
            log.info("worker: session %s usage: %s", session_id, summary)
        except Exception:
            log.exception("worker: usage summary failed for %s", session_id)

        # Recover answers the save_answer tool never committed (model forgot to
        # call it, or the candidate hung up mid-question) from the verbatim
        # transcript — otherwise real answers are dropped and the session lands
        # on "no_answers" with no report.
        recovered = state.reconstruct_answers(userdata)
        if recovered:
            log.info(
                "worker: session %s recovered %d answer(s) from transcript",
                session_id,
                recovered,
            )

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
            import httpx

            req = ScoreRequest(session_id=session_id)
            score_timeout = httpx.Timeout(10.0, read=600.0)
            async with httpx.AsyncClient(timeout=score_timeout) as client:
                await client.post(
                    f"{api_base}/api/score",
                    json=req.model_dump(),
                    headers=_internal_headers(settings),
                )
        except Exception:
            log.exception("worker: scoring trigger failed for %s", session_id)

    ctx.add_shutdown_callback(_on_shutdown)

    room_options = build_room_options(settings)
    start_kwargs = {"room_options": room_options} if room_options is not None else {}
    await session.start(
        agent=Interviewer(userdata),
        room=ctx.room,
        **start_kwargs,
    )

    # Start the guard only once the session is live (it calls session.say /
    # session.shutdown); it runs detached until a ceiling trips or shutdown.
    guard.start()
    # Checkpoint the transcript off the turn path so a hard crash (before the
    # shutdown callback) loses at most one interval, not the whole interview.
    flusher.start()


def main() -> None:
    # livekit-agents reads LIVEKIT_URL/API_KEY/API_SECRET from os.environ; we keep
    # them in Settings (.env), so pass them through explicitly to WorkerOptions.
    settings = get_settings()
    init_observability(settings)
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            ws_url=settings.livekit_url,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
            # Explicit-dispatch name: the web token's roomConfig.agents requests
            # THIS name, and LiveKit Cloud Agents routes the job to the worker
            # registered under it. Without it the room joins with no agent
            # listening ("Connecting your interviewer…" forever, issue #67).
            # Local `livekit-server --dev` honors the same dispatch, so the
            # local path keeps working once the token carries roomConfig.
            agent_name=getattr(settings, "livekit_agent_name", None)
            or "deepinterview-interviewer",
            # All persistence (transcript + context + scoring trigger) happens in
            # the shutdown callback; the SDK default 10s can kill the job process
            # mid-write (the live-result POST alone allows 20s). Give shutdown
            # real headroom so a graceful drain finishes persisting.
            shutdown_process_timeout=settings.shutdown_process_timeout_sec,
        )
    )


if __name__ == "__main__":
    main()
