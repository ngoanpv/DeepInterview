"""LLM adapter factory + real adapters (lazy-imported SDKs).

``get_llm(settings)`` returns the deterministic :class:`MockLLM` unless an LLM
provider is selected *and* its API key is present; otherwise it logs a warning
and falls back to the mock. Real adapters import their SDK inside methods so the
module imports cleanly with no SDK installed.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from ..logging import get_logger
from .base import LLMAdapter
from .mock import MockLLM

if TYPE_CHECKING:
    from ..config import Settings

log = get_logger(__name__)

# Per-call ceiling so a stalled provider call can never hang a pipeline forever
# (the prep graph's per-node try/except only fires once the call RETURNS).
_DEFAULT_TIMEOUT_SEC = 90.0


def _schema_prompt(system: str, schema: type) -> str:
    """Append the JSON Schema to the system prompt (provider-agnostic).

    Both Gemini's ``response_schema`` and OpenAI's strict structured outputs
    reject free-form maps like our ``LocalizedText = dict[str, str]``
    (additionalProperties), so the reliable cross-provider pattern is JSON mode
    + the schema in the prompt + Pydantic validation of the result.
    """
    schema_json = json.dumps(schema.model_json_schema())
    return (
        f"{system}\n\nReturn ONLY a single JSON value that conforms to this "
        f"JSON Schema (no markdown, no commentary):\n{schema_json}"
    )


def _loads_json(text: str) -> Any:
    """Parse JSON from an LLM response, tolerating ```json fences, stray prose, and
    *trailing* "Extra data".

    The keystone failure this fixes: the question planner has the largest schema,
    so its real Gemini response is the biggest — and a complete JSON object was
    sometimes FOLLOWED by extra content (a second object / trailing commentary).
    Plain ``json.loads`` raises ``Extra data`` on that, and the old greedy
    ``\\{.*\\}`` fallback spanned to the LAST brace (swallowing the trailing junk
    into invalid JSON), so every plan silently fell back to the generic mock —
    an interview that asks one question literally titled "mock". ``raw_decode``
    returns the FIRST complete JSON value and ignores anything after it.
    """
    import re  # noqa: PLC0415

    t = (text or "").strip()
    # Strip a wrapping ```json ... ``` / ``` ... ``` markdown fence, if present.
    if t.startswith("```"):
        t = re.sub(r"^```[^\n]*\n?", "", t)
        t = re.sub(r"\n?```\s*$", "", t).strip()
    # Fast path: a single clean JSON value.
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    # Tolerant path: decode the first complete JSON value starting at the first
    # '{' or '[', ignoring any trailing data (raw_decode is "Extra data"-safe).
    decoder = json.JSONDecoder()
    for i, ch in enumerate(t):
        if ch in "{[":
            try:
                obj, _end = decoder.raw_decode(t, i)
                return obj
            except json.JSONDecodeError:
                continue
    raise json.JSONDecodeError("no JSON value found in LLM response", t, 0)


class GeminiLLM:
    """Google Gemini via ``google-genai`` (lazy import)."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3-flash-preview",
        timeout_sec: float = _DEFAULT_TIMEOUT_SEC,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_sec

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
        resp = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=self._model,
                contents=user,
                config={"system_instruction": system},
            ),
            timeout=self._timeout,
        )
        return resp.text or ""

    async def complete_json(self, *, system: str, user: str, schema: type) -> Any:
        # JSON mode + schema-in-prompt (see _schema_prompt for why not
        # ``response_schema``).
        client = self._client()
        resp = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=self._model,
                contents=user,
                config={
                    "system_instruction": _schema_prompt(system, schema),
                    "response_mime_type": "application/json",
                },
            ),
            timeout=self._timeout,
        )
        return schema.model_validate(_loads_json(resp.text or "{}"))


class OpenAILLM:
    """OpenAI via the ``openai`` SDK (lazy import)."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5.1-mini",
        timeout_sec: float = _DEFAULT_TIMEOUT_SEC,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_sec

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
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            ),
            timeout=self._timeout,
        )
        return resp.choices[0].message.content or ""

    async def complete_json(self, *, system: str, user: str, schema: type) -> Any:
        # JSON mode + schema-in-prompt, NOT strict structured outputs: OpenAI's
        # strict mode rejects free-form maps (additionalProperties) like our
        # ``LocalizedText = dict[str, str]``, which would silently break the
        # question planner (every plan falling back to mock). Same pattern as
        # the Gemini adapter; Pydantic validates the result either way.
        client = self._client()
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _schema_prompt(system, schema)},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
            ),
            timeout=self._timeout,
        )
        return schema.model_validate(_loads_json(resp.choices[0].message.content or "{}"))


def get_llm(settings: Settings) -> LLMAdapter:
    """Choose an LLM adapter from settings, falling back to the mock."""
    provider = (settings.llm_provider or "mock").lower()
    if provider == "mock":
        return MockLLM()
    timeout = getattr(settings, "llm_call_timeout_sec", _DEFAULT_TIMEOUT_SEC)
    if provider == "gemini":
        if settings.gemini_api_key:
            return GeminiLLM(settings.gemini_api_key, settings.gemini_model, timeout)
        log.warning("llm_provider=gemini but gemini_api_key is missing; using MockLLM.")
        return MockLLM()
    if provider == "openai":
        if settings.openai_api_key:
            return OpenAILLM(settings.openai_api_key, settings.openai_model, timeout)
        log.warning("llm_provider=openai but openai_api_key is missing; using MockLLM.")
        return MockLLM()
    log.warning("Unknown llm_provider=%r; using MockLLM.", provider)
    return MockLLM()
