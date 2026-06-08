"""Adapter protocols and shared adapter types.

Every external provider is hidden behind one of these ``Protocol``s. The default
implementations (see ``mock.py``) are deterministic and require no network, so
the whole stack builds and tests green with zero API keys / SDKs installed.
STT and TTS adapters are added by WP-5 (the live voice loop).
"""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str


@runtime_checkable
class LLMAdapter(Protocol):
    """Text + structured-JSON completion."""

    async def complete_text(self, *, system: str, user: str) -> str: ...

    async def complete_json(self, *, system: str, user: str, schema: type[T]) -> T: ...


@runtime_checkable
class SearchAdapter(Protocol):
    """Web search for company research."""

    async def search(
        self, query: str, *, lang: str = "en", max_results: int = 6
    ) -> list[SearchResult]: ...


@runtime_checkable
class EmbeddingsAdapter(Protocol):
    """Text embeddings for the knowledge layer."""

    async def embed(self, texts: list[str]) -> list[list[float]]: ...
