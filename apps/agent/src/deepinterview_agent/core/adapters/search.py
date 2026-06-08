"""Search adapter factory + real adapters (lazy-imported SDKs).

``get_search(settings)`` returns :class:`MockSearch` unless a search provider is
selected *and* its key is present; otherwise it logs and falls back to the mock.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..logging import get_logger
from .base import SearchAdapter, SearchResult
from .mock import MockSearch

if TYPE_CHECKING:
    from ..config import Settings

log = get_logger(__name__)


class TavilySearch:
    """Tavily web search via ``tavily-python`` (lazy import)."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def _client(self) -> Any:
        try:
            from tavily import TavilyClient  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - depends on optional SDK
            raise RuntimeError(
                "tavily-python is not installed; install the 'tavily' extra."
            ) from exc
        return TavilyClient(api_key=self._api_key)

    async def search(
        self, query: str, *, lang: str = "en", max_results: int = 6
    ) -> list[SearchResult]:
        import asyncio  # noqa: PLC0415

        client = self._client()

        def _run() -> dict[str, Any]:
            return client.search(query=query, max_results=max_results)

        data = await asyncio.to_thread(_run)
        results: list[SearchResult] = []
        for item in data.get("results", []):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                )
            )
        return results


def get_search(settings: Settings) -> SearchAdapter:
    """Choose a search adapter from settings, falling back to the mock."""
    provider = (settings.search_provider or "mock").lower()
    if provider == "mock":
        return MockSearch()
    if provider == "tavily":
        if settings.tavily_api_key:
            return TavilySearch(settings.tavily_api_key)
        log.warning("search_provider=tavily but tavily_api_key is missing; using MockSearch.")
        return MockSearch()
    log.warning("Unknown search_provider=%r; using MockSearch.", provider)
    return MockSearch()
