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
    gemini_model_live: str = "gemini-flash-lite-latest"
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

    # --- service -------------------------------------------------------------
    agent_api_port: int = 8000
    default_language: str = "en"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance loaded from env / ``.env``."""
    return Settings()
