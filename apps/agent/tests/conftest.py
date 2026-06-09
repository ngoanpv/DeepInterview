"""Pytest configuration: pin the offline suite to the deterministic mock stack.

Every test module here is documented as offline/MockLLM (no API keys, no network)
and several assert run-to-run determinism (e.g. ``test_run_score_is_stable_on_rerun``).
The repo ships a real ``apps/agent/.env`` with live keys and ``LLM_PROVIDER=gemini``
for the live worker; ``pydantic-settings`` would load that and make ``build_deps()``
return the real, non-deterministic Gemini adapter — breaking the determinism tests
and turning a 4-second suite into a multi-minute one that hammers the live key.

We force every provider to ``mock`` via ``os.environ`` BEFORE any test imports
``get_settings()`` (whose result is ``lru_cache``d). ``os.environ`` takes precedence
over ``.env`` in pydantic-settings, so this restores the documented offline contract
regardless of what ``.env`` contains. We likewise BLANK the Supabase creds so
``get_repository()`` falls back to the in-memory repo: a real ``.env`` now ships a
Supabase URL + service-role key, and without this the suite would select
``SupabaseRepository`` and fail on the optional ``supabase`` SDK (not installed in
the test venv). Set ``DEEPINTERVIEW_TEST_USE_ENV=1`` to opt out (e.g. a deliberate
live integration run).
"""

from __future__ import annotations

import os

if os.environ.get("DEEPINTERVIEW_TEST_USE_ENV") != "1":
    for _var in (
        "LLM_PROVIDER",
        "STT_PROVIDER",
        "TTS_PROVIDER",
        "SEARCH_PROVIDER",
        "EMBEDDINGS_PROVIDER",
    ):
        os.environ[_var] = "mock"
    # Empty string overrides ``.env`` and is falsy, so the
    # ``settings.supabase_url and settings.supabase_service_role_key`` guard in
    # ``get_repository()`` is False → deterministic in-memory ``MemoryRepository``.
    for _var in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
        os.environ[_var] = ""
