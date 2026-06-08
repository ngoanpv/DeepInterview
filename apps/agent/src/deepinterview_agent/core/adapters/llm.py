"""LLM adapter factory + real adapters (lazy-imported SDKs).

``get_llm(settings)`` returns the deterministic :class:`MockLLM` unless an LLM
provider is selected *and* its API key is present; otherwise it logs a warning
and falls back to the mock. Real adapters import their SDK inside methods so the
module imports cleanly with no SDK installed.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from ..logging import get_logger
from .base import LLMAdapter
from .mock import MockLLM

if TYPE_CHECKING:
    from ..config import Settings

log = get_logger(__name__)


def _loads_json(text: str) -> Any:
    """Parse JSON from an LLM response, tolerating ```json fences / stray prose."""
    t = (text or "").strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        import re  # noqa: PLC0415

        m = re.search(r"\{.*\}|\[.*\]", t, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


class GeminiLLM:
    """Google Gemini via ``google-genai`` (lazy import)."""

    def __init__(self, api_key: str, model: str = "gemini-3-flash-preview") -> None:
        self._api_key = api_key
        self._model = model

    def _client(self) -> Any:
        try:
            from google import genai  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - depends on optional SDK
            raise RuntimeError(
                "google-genai is not installed; install the 'gemini' extra."
            ) from exc
        return genai.Client(api_key=self._api_key)

    async def complete_text(self, *, system: str, user: str) -> str:
        client = self._client()
        resp = await client.aio.models.generate_content(
            model=self._model,
            contents=user,
            config={"system_instruction": system},
        )
        return resp.text or ""

    async def complete_json(self, *, system: str, user: str, schema: type) -> Any:
        # Embed the JSON Schema in the prompt instead of Gemini's
        # ``response_schema`` (an OpenAPI subset that rejects free-form maps like
        # our ``LocalizedText = dict[str, str]`` and ignores Pydantic validators).
        client = self._client()
        schema_json = json.dumps(schema.model_json_schema())
        full_system = (
            f"{system}\n\nReturn ONLY a single JSON value that conforms to this "
            f"JSON Schema (no markdown, no commentary):\n{schema_json}"
        )
        resp = await client.aio.models.generate_content(
            model=self._model,
            contents=user,
            config={
                "system_instruction": full_system,
                "response_mime_type": "application/json",
            },
        )
        return schema.model_validate(_loads_json(resp.text or "{}"))


class OpenAILLM:
    """OpenAI via the ``openai`` SDK (lazy import)."""

    def __init__(self, api_key: str, model: str = "gpt-5.1-mini") -> None:
        self._api_key = api_key
        self._model = model

    def _client(self) -> Any:
        try:
            from openai import AsyncOpenAI  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - depends on optional SDK
            raise RuntimeError(
                "openai is not installed; install the 'openai' extra."
            ) from exc
        return AsyncOpenAI(api_key=self._api_key)

    async def complete_text(self, *, system: str, user: str) -> str:
        client = self._client()
        resp = await client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""

    async def complete_json(self, *, system: str, user: str, schema: type) -> Any:
        client = self._client()
        resp = await client.beta.chat.completions.parse(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format=schema,
        )
        parsed = resp.choices[0].message.parsed
        if parsed is None:
            raise RuntimeError("OpenAI returned no parsed structured output.")
        return parsed


def get_llm(settings: Settings) -> LLMAdapter:
    """Choose an LLM adapter from settings, falling back to the mock."""
    provider = (settings.llm_provider or "mock").lower()
    if provider == "mock":
        return MockLLM()
    if provider == "gemini":
        if settings.gemini_api_key:
            return GeminiLLM(settings.gemini_api_key, settings.gemini_model)
        log.warning("llm_provider=gemini but gemini_api_key is missing; using MockLLM.")
        return MockLLM()
    if provider == "openai":
        if settings.openai_api_key:
            return OpenAILLM(settings.openai_api_key, settings.openai_model)
        log.warning("llm_provider=openai but openai_api_key is missing; using MockLLM.")
        return MockLLM()
    log.warning("Unknown llm_provider=%r; using MockLLM.", provider)
    return MockLLM()
