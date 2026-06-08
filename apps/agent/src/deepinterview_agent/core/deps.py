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


def build_deps(settings: Settings | None = None) -> Deps:
    """Assemble the dependency bundle (defaults to cached settings)."""
    settings = settings or get_settings()
    return Deps(
        settings=settings,
        llm=get_llm(settings),
        search=get_search(settings),
        embeddings=get_embeddings(settings),
        knowledge=get_knowledge(settings),
        repo=get_repository(settings),
    )
