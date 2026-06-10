"""Dependency bundle wiring config + adapters + persistence together.

Pipelines and API routes receive a single :class:`Deps` instance, so swapping a
provider (mock vs real) is a config concern, not a code concern.
"""

from __future__ import annotations

from dataclasses import dataclass

from .adapters.base import EmbeddingsAdapter, LLMAdapter, SearchAdapter
from .adapters.embeddings import get_embeddings
from .adapters.knowledge import KnowledgeClient, get_knowledge
from .adapters.llm import get_llm
from .adapters.search import get_search
from .config import Settings, get_settings
from .persistence.repository import SessionRepository, get_repository


@dataclass
class Deps:
    settings: Settings
    llm: LLMAdapter
    search: SearchAdapter
    embeddings: EmbeddingsAdapter
    knowledge: KnowledgeClient
    repo: SessionRepository


def _assemble(settings: Settings) -> Deps:
    return Deps(
        settings=settings,
        llm=get_llm(settings),
        search=get_search(settings),
        embeddings=get_embeddings(settings),
        knowledge=get_knowledge(settings),
        repo=get_repository(settings),
    )


# Cached default bundle: API routes call build_deps() per request, and without
# this every request rebuilt every adapter INCLUDING a fresh Supabase client
# (new HTTP connection pool per request). Keyed on the get_settings() instance
# so clearing the settings cache (tests) transparently invalidates this too.
_default_deps: Deps | None = None


def build_deps(settings: Settings | None = None) -> Deps:
    """Assemble the dependency bundle (defaults to cached settings + cached deps)."""
    global _default_deps  # noqa: PLW0603 - module-level cache, see comment above
    if settings is not None:
        return _assemble(settings)
    current = get_settings()
    if _default_deps is None or _default_deps.settings is not current:
        _default_deps = _assemble(current)
    return _default_deps
