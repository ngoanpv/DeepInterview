"""Embeddings adapter factory + real adapters (lazy-imported SDKs).

``get_embeddings(settings)`` returns :class:`MockEmbeddings` unless an embeddings
provider is selected *and* its key is present; otherwise it logs and falls back
to the mock.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..logging import get_logger
from .base import EmbeddingsAdapter
from .mock import MockEmbeddings

if TYPE_CHECKING:
    from ..config import Settings

log = get_logger(__name__)


class OpenAIEmbeddings:
    """OpenAI embeddings via the ``openai`` SDK (lazy import)."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def _client(self) -> Any:
        try:
            from openai import AsyncOpenAI  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - depends on optional SDK
            raise RuntimeError(
                "openai is not installed; install the 'openai' extra."
            ) from exc
        return AsyncOpenAI(api_key=self._api_key)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        client = self._client()
        resp = await client.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        return [item.embedding for item in resp.data]


def get_embeddings(settings: Settings) -> EmbeddingsAdapter:
    """Choose an embeddings adapter from settings, falling back to the mock."""
    provider = (settings.embeddings_provider or "mock").lower()
    if provider == "mock":
        return MockEmbeddings()
    if provider == "openai":
        if settings.openai_api_key:
            return OpenAIEmbeddings(settings.openai_api_key)
        log.warning(
            "embeddings_provider=openai but openai_api_key is missing; using MockEmbeddings."
        )
        return MockEmbeddings()
    log.warning("Unknown embeddings_provider=%r; using MockEmbeddings.", provider)
    return MockEmbeddings()
