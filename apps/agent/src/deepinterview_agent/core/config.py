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
    gemini_model: str = "gemini-3-flash-preview"
    # Live tier MUST be a Gemini 2.x model: the live loop uses function tools, and
    # Gemini 3 requires "thought_signatures" in function-call turns that
    # livekit-plugins-google 1.5.x does not thread yet (-> 400 INVALID_ARGUMENT).
    # 2.5-flash-lite is low-latency and function-calls cleanly. Override: GEMINI_MODEL_LIVE.
    gemini_model_live: str = "gemini-2.5-flash-lite"
    # 2026-current OpenAI default. UNVERIFIED — no OpenAI key in this env; re-verify
    # the exact id + structured-output support before wiring billing (CLAUDE.md
    # golden rule #6). Env-overridable via OPENAI_MODEL.
    openai_model: str = "gpt-5.1-mini"

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

    # --- knowledge (LightRAG sidecar) ----------------------------------------
    # When set, the knowledge adapter + /api/kb/ingest forward to this base URL;
    # unset (the default) keeps everything fully offline. Env-overridable via
    # LIGHTRAG_URL (pydantic-settings reads it by field name).
    lightrag_url: str | None = None

    # --- service -------------------------------------------------------------
    agent_api_port: int = 8000
    default_language: str = "en"

    # --- feature flags -------------------------------------------------------
    # Voice Study Coach: when true, the spoken coach worker (worker_coach.py)
    # wires the grounded knowledge-base function tool into the live session.
    # OFF by default so the default config stays fully offline and the coach
    # turn path stays lean. Override: ENABLE_COACH_KB=true.
    enable_coach_kb: bool = False

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

    # --- live cost / duration guard (Golden Rule #5: cap voice in code) -------
    # Hard ceilings enforced by the worker's SessionGuard so a live room can
    # never run unbounded (a stalled/looping LLM would otherwise burn voice
    # minutes forever). These are the in-code per-tier caps; a per-session
    # override can later be threaded in via RoomMetadata.
    max_interview_duration_sec: int = 1200  # 20 min wall-clock hard stop
    max_interview_turns: int = 80  # transcript turns hard stop

    # --- post / scoring resilience -------------------------------------------
    # Per-stage timeout for the (latency-tolerant) scoring pipeline; on timeout
    # or error the stage degrades to a valid fallback instead of failing the
    # whole scorecard. See post/__init__.py.
    score_stage_timeout_sec: float = 60.0
    # Closed-loop skill distiller (WP-10): when enabled, a scored interview
    # proposes a playbook delta into the review queue. OFF by default so tests
    # and local runs don't write drafts; enable in production via env.
    enable_skill_distiller: bool = False


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance loaded from env / ``.env``."""
    return Settings()
