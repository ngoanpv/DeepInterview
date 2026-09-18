"""Application settings.

All fields are optional so the app boots with ZERO environment configured: every
provider defaults to ``"mock"`` and every key is ``None``. Real providers are
opt-in via env vars; if a provider is selected but its key is missing, the
adapter factories log a warning and fall back to the deterministic mock.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- provider selection (mock by default = fully offline) ----------------
    llm_provider: str = "mock"
    stt_provider: str = "mock"
    tts_provider: str = "mock"
    search_provider: str = "mock"
    embeddings_provider: str = "mock"

    # --- model overrides (swap models without code changes via env) ----------
    # Two tiers, per the prep/live/post split:
    #   gemini_model      = analytic/background (prep, scoring) — newest Gemini 3
    #                       Flash (has "thinking"); verified for structured output.
    #   gemini_model_live = the real-time interviewer — lowest-latency flash-lite.
    # Ids verified against the models API 2026-07-25 (project golden rule #6).
    gemini_model: str = "gemini-3.6-flash"
    # Newest flash-lite. Gemini 3.x on the live path needs livekit-plugins-google
    # >=1.6, which threads the "thought_signature" through function-call turns
    # (1.5.x dropped it -> 400 INVALID_ARGUMENT after the first save_answer).
    # Pin an exact id here, never a "-latest" alias: the live loop's function
    # calling must not change models under us. Override: GEMINI_MODEL_LIVE.
    gemini_model_live: str = "gemini-3.5-flash-lite"
    # Gemini native TTS — the fallback voice for languages Cartesia doesn't cover
    # (e.g. Vietnamese). gemini-2.5-flash-preview-tts speaks 24 languages incl.
    # vi-VN. Override via GEMINI_TTS_MODEL when a newer TTS model ships.
    gemini_tts_model: str = "gemini-2.5-flash-preview-tts"
    # 2026-current OpenAI default. UNVERIFIED — no OpenAI key in this env; re-verify
    # the exact id + structured-output support before wiring billing (project
    # golden rule #6). Env-overridable via OPENAI_MODEL.
    openai_model: str = "gpt-5.1-mini"
    # ElevenLabs TTS model — the low-latency multilingual voice for languages
    # Cartesia can't speak (e.g. Vietnamese). eleven_flash_v2_5 is ~75ms-latency
    # and covers 32 languages incl. vi. Override via ELEVENLABS_MODEL.
    elevenlabs_model: str = "eleven_flash_v2_5"

    # --- local (self-hosted) model servers ------------------------------------
    # The "runs 100% local, no cloud model keys" path. All three speak the
    # OpenAI HTTP shape, so they reuse the already-installed openai SDK +
    # livekit-plugins-openai with a `base_url` override — no extra dependency.
    #   ollama  -> LLM   (prep, scoring, and the live turn path)
    #   whisper -> STT   (any OpenAI-compatible /v1/audio/transcriptions server)
    #   kokoro  -> TTS   (kokoro-fastapi's /v1/audio/speech)
    # Select them with LLM_PROVIDER=ollama / STT_PROVIDER=whisper /
    # TTS_PROVIDER=kokoro; each needs its base URL, never an API key.
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen3:8b"
    # Live tier, mirroring gemini_model / gemini_model_live: prep and scoring can
    # afford a bigger model because nobody is waiting mid-sentence; the turn loop
    # cannot. A smaller model here buys time-to-first-token on every turn.
    #
    # Deliberately EMPTY rather than a smaller default: unlike a cloud tier, the
    # live model has to already be pulled on this machine. Defaulting to
    # something like qwen3:4b would 404 the turn path for everyone who pulled
    # only qwen3:8b — the "it worked yesterday" upgrade break. Empty means "same
    # model as prep", so the local path behaves exactly as before until you opt
    # in. Override: OLLAMA_MODEL_LIVE.
    ollama_model_live: str = ""
    whisper_base_url: str = "http://localhost:8000/v1"
    # `base` (multilingual), NOT `small`. Measured on an M5 Pro with the LLM
    # generating concurrently — the condition that actually holds mid-interview,
    # since the next utterance is transcribed while the agent is still replying:
    #   tiny.en  0.06x realtime idle / 0.13x under load
    #   base     0.09x                / ~0.7x
    #   small    0.40x                / 0.77x, ~3.4 GB resident
    # The plugin hard-codes a 30s read timeout that no setting can raise, so the
    # headroom has to come from the model. `small` in a memory-constrained
    # Docker VM blew straight through it and the turn died with
    # "failed to recognize speech". `base` is ~10x lighter and just as accurate
    # on interview speech. Use `small`/`medium` only with a GPU.
    whisper_model: str = "Systran/faster-whisper-base"
    kokoro_base_url: str = "http://localhost:8880/v1"
    # MUST stay in the openai plugin's AUDIO_STREAM_MODELS = {"tts-1","tts-1-hd"}.
    # Any other id routes synthesis down its SSE branch, which parses "data:"
    # lines: raw audio matches nothing, the stream drains, and the agent emits
    # NO AUDIO AND NO EXCEPTION. kokoro-fastapi ignores the model name, so
    # "tts-1" is purely the switch that selects the audio-bytes path.
    kokoro_model: str = "tts-1"
    # Blank = pick the voice from the session language (worker._KOKORO_VOICE),
    # since Kokoro encodes the language in the voice-id prefix. Set it to pin one.
    kokoro_voice: str = ""
    # The plugin hard-codes a 24 kHz decode (openai/tts.py SAMPLE_RATE), which
    # is also Kokoro-82M's native rate. Raw PCM avoids a decode step; a
    # mismatched rate here produces chipmunk/slow-motion speech, not an error.
    kokoro_response_format: str = "pcm"
    # Non-empty placeholder credential for local servers, which need no auth.
    # It must not be "": the openai plugin raises ValueError on an
    # explicitly-passed empty key (stt.py/tts.py "OpenAI API key is required").
    local_api_key: str = "local"
    # One-shot reachability probe before a live session starts. A local server
    # that isn't running is the local path's equivalent of a missing API key,
    # and without this the candidate joins and *then* the first turn errors.
    local_probe_timeout_sec: float = 2.0
    # Per-request ceiling on the LIVE path when a local provider is selected.
    # The SDK's APIConnectOptions default is 10s, which a cloud model always
    # beats but a local one — cold, or generating on a shared GPU — does not:
    # every turn would abort before the first token. Applied only when a local
    # provider is in play, so the cloud path keeps the SDK default.
    local_provider_timeout_sec: float = 30.0

    # --- provider credentials (all optional) ---------------------------------
    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    soniox_api_key: str | None = None
    deepgram_api_key: str | None = None
    cartesia_api_key: str | None = None
    elevenlabs_api_key: str | None = None
    tavily_api_key: str | None = None
    exa_api_key: str | None = None

    # --- supabase ------------------------------------------------------------
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None

    # --- livekit -------------------------------------------------------------
    livekit_url: str | None = None
    livekit_api_key: str | None = None
    livekit_api_secret: str | None = None
    # Dispatch name the worker registers under. MUST match the web token's
    # `roomConfig.agents[0].agentName` (LIVEKIT_AGENT_NAME) — explicit dispatch
    # is how LiveKit Cloud Agents routes a job to this worker. Without it the
    # room joins with no agent listening ("Connecting your interviewer…"
    # forever, issue #67).
    livekit_agent_name: str = "deepinterview-interviewer"

    # --- knowledge (LightRAG sidecar) ----------------------------------------
    # When set, the knowledge adapter + /api/kb/ingest forward to this base URL;
    # unset (the default) keeps everything fully offline. Env-overridable via
    # LIGHTRAG_URL (pydantic-settings reads it by field name).
    lightrag_url: str | None = None
    # Optional shared secret sent as ``X-Internal-Secret`` when calling the
    # sidecar. When the sidecar has LIGHTRAG_API_SECRET set it rejects mismatches;
    # unset here (and there) keeps the offline/local path open. Set both to the
    # same value in a hosted deployment.
    lightrag_api_secret: str | None = None

    # --- internal API auth (opt-in) ------------------------------------------
    # The agent API is trust-the-network by design (reads are capability-guarded
    # by unguessable session ids). When INTERNAL_API_SECRET is set, the *write*
    # endpoints (prep/score/coach/kb-ingest and the worker's live-result
    # write-back) require it in the ``X-Internal-Secret`` header; unset (the
    # default) leaves them open so zero-config local runs and tests are
    # unaffected. The web app and the voice worker send it when configured.
    internal_api_secret: str | None = None

    # --- service -------------------------------------------------------------
    agent_api_port: int = 8000
    # Base URL the WORKER uses to reach the prep/score API. Defaults to
    # localhost:{agent_api_port} (same-host dev); docker compose overrides it to
    # the service DNS name (AGENT_API_URL=http://agent-api:8000) because the
    # worker runs in a separate container where localhost is itself.
    agent_api_url: str | None = None
    default_language: str = "en"

    # --- LLM call resilience --------------------------------------------------
    # Per-call ceiling on prep/post LLM requests. Without it a stalled provider
    # call hangs the prep graph forever and the session sticks in "prep" (the
    # node-level try/except only fires once the call RETURNS). The post pipeline
    # additionally has per-stage timeouts.
    llm_call_timeout_sec: float = 90.0

    # --- live: adaptive interview (off the turn-critical path) ----------------
    # When on, the background Director caches an advisory difficulty
    # recommendation and the interviewer exposes a get_difficulty_hint tool. The
    # turn path never blocks on it. Default OFF so the lean live loop and the
    # offline suite are unchanged. Override via ENABLE_ADAPTIVE_DIFFICULTY.
    enable_adaptive_difficulty: bool = False

    # --- post: adversarial score verifier (off the turn-critical path) --------
    # When on, the post scoring pipeline runs a second, adversarial LLM pass over
    # low/borderline competency scores to catch over- or under-scoring; any
    # failure leaves the original scores untouched. Default OFF so the offline
    # suite and existing scorecards are unchanged. Override via
    # ENABLE_SCORE_VERIFIER / SCORE_VERIFIER_TIMEOUT_SEC.
    enable_score_verifier: bool = False
    score_verifier_timeout_sec: float = 60.0

    # --- live: BVC noise cancellation (opt-in) --------------------------------
    # OFF by default: the BVC native filter failed to initialize inside the
    # slim arm64 container ("failed to initialize the audio filter") and took
    # the whole input audio stream down with it — the agent heard nothing.
    # Enable with ENABLE_BVC=true only on hosts where it's verified to load.
    # Noise robustness without it: semantic turn detector + min_words gate.
    enable_bvc: bool = False

    # --- live cost / duration guard (Golden Rule #5: cap voice in code) -------
    # Hard ceilings enforced by the worker's SessionGuard so a live room can
    # never run unbounded (a stalled/looping LLM would otherwise burn voice
    # minutes forever). These are the in-code per-tier caps; a per-session
    # override can later be threaded in via RoomMetadata.
    max_interview_duration_sec: int = 1200  # 20 min wall-clock hard stop
    max_interview_turns: int = 80  # transcript turns hard stop

    # --- live: durability -----------------------------------------------------
    # All persistence normally happens in the worker's shutdown callback. Two
    # settings harden that against a hard crash (OOM/SIGKILL) that skips it:
    #   shutdown_process_timeout_sec — how long the SDK lets the shutdown
    #     callback run before killing the job process. The SDK default (10s) can
    #     kill it mid-write (the live-result POST alone allows 20s); give it real
    #     headroom.
    #   transcript_flush_interval_sec — off-turn-path checkpoint cadence. Every
    #     interval, if the transcript grew, the worker POSTs a partial result to
    #     the live-result endpoint, so a crash loses at most one interval of
    #     conversation instead of the whole interview. 0 disables it.
    shutdown_process_timeout_sec: float = 60.0
    transcript_flush_interval_sec: float = 20.0

    # --- post / scoring resilience -------------------------------------------
    # Per-stage timeout for the (latency-tolerant) scoring pipeline; on timeout
    # or error the stage degrades to a valid fallback instead of failing the
    # whole scorecard. See post/__init__.py.
    score_stage_timeout_sec: float = 60.0
    # Closed-loop skill distiller (WP-10): when enabled, a scored interview
    # proposes a playbook delta into the review queue. OFF by default so tests
    # and local runs don't write drafts; enable in production via env.
    enable_skill_distiller: bool = False

    # --- tracing (WP-12: local JSONL + optional Langfuse) ---------------------
    # Local trace files are the default "easy tracking" tool: every prep/score/
    # live run appends spans to TRACE_DIR/<trace_id>.jsonl, readable offline via
    # `deepinterview traces` (CLI) and GET /api/traces. No extra deps, never
    # raises. Set TRACE_ENABLED=0 to disable (the test suite does this).
    trace_enabled: bool = True
    trace_dir: str = ".deepinterview/traces"
    # When True, LLM spans also store short prompt previews (first 500 chars).
    # Default OFF so trace files never hold full CVs/JDs (lengths always logged).
    trace_include_prompts: bool = False
    # Langfuse forwarder (opt-in hosted trace UI): when both keys are set AND
    # the `observability` extra is installed, spans are additionally emitted as
    # OTel spans which Langfuse v4 captures. Env: LANGFUSE_PUBLIC_KEY etc.
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str | None = None
    sentry_dsn: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance loaded from env / ``.env``."""
    return Settings()
