"""Deterministic, offline adapter implementations.

These are the defaults. They never touch the network and never import a provider
SDK, so the entire app imports and tests green with zero keys installed.

The interesting piece is :func:`build_mock` / ``MockLLM.complete_json``: given any
Pydantic model class it constructs a *minimal valid instance* by walking
``model_fields`` and supplying a value for every required field only (fields with
defaults are left to their default). For every required list it emits exactly one
recursively-built element, which uniformly satisfies the "non-empty" intent for
``QuestionPlan.questions``, ``PlannedQuestion.rubric``/``followups`` etc. The only
runtime refinement in the shared models is ``LocalizedText`` needing an ``en`` key,
which the dict branch supplies.
"""

from __future__ import annotations

import hashlib
import struct
import types
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel

from .base import SearchResult

_NoneType = type(None)


def _unwrap_optional(annotation: Any) -> Any:
    """If ``annotation`` is ``X | None`` return ``X``; otherwise return it as-is."""
    origin = get_origin(annotation)
    # ``X | None`` (PEP 604) yields ``types.UnionType``; ``Optional[X]`` yields ``Union``.
    if origin is Union or origin is types.UnionType:
        non_null = [a for a in get_args(annotation) if a is not _NoneType]
        if len(non_null) == 1:
            return non_null[0]
    return annotation


def _build_value(annotation: Any) -> Any:
    """Build a minimal valid value for a (non-optional) type annotation."""
    annotation = _unwrap_optional(annotation)
    origin = get_origin(annotation)

    # Literal[...] / enum-like -> first member.
    if origin is Literal:
        return get_args(annotation)[0]

    # Containers.
    if origin in (list, tuple, set, frozenset):
        args = get_args(annotation)
        elem = _build_value(args[0]) if args else "mock"
        return [elem]
    if origin is dict:
        # The only dict field in the shared models is LocalizedText.
        return {"en": "mock"}

    # Nested Pydantic model -> recurse.
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return build_mock(annotation).model_dump()

    # Scalars.
    if annotation is bool:
        return False
    if annotation is int:
        return 1
    if annotation is float:
        return 0.5
    if annotation is str:
        return "mock"
    if annotation is dict:
        return {"en": "mock"}

    # Fallback for anything unexpected.
    return "mock"


def build_mock(schema: type[BaseModel]) -> BaseModel:
    """Construct a minimal *valid* instance of ``schema``.

    Only required fields are populated; fields with defaults keep their default.
    The ``difficulty`` field is pinned to ``3`` (a sensible mid value within the
    documented 1-5 range, even though the model itself does not constrain it).
    """
    built: dict[str, Any] = {}
    for name, field in schema.model_fields.items():
        if not field.is_required():
            continue
        if name == "difficulty":
            built[name] = 3
            continue
        built[name] = _build_value(field.annotation)
    return schema.model_validate(built)


class MockLLM:
    """Deterministic LLM: canned text and schema-valid structured output."""

    async def complete_text(self, *, system: str, user: str) -> str:
        return "This is a deterministic mock completion."

    async def complete_json(self, *, system: str, user: str, schema: type) -> Any:
        return build_mock(schema)


class MockSearch:
    """Deterministic search returning a fixed, query-derived result set."""

    async def search(
        self, query: str, *, lang: str = "en", max_results: int = 6
    ) -> list[SearchResult]:
        n = max(1, min(max_results, 3))
        return [
            SearchResult(
                title=f"Mock result {i + 1} for {query}",
                url=f"https://example.com/mock/{i + 1}",
                snippet=f"Deterministic mock snippet {i + 1} about {query} ({lang}).",
            )
            for i in range(n)
        ]


class MockEmbeddings:
    """Deterministic embeddings: hashlib-derived fixed 8-dim vector per text."""

    DIM = 8

    def _vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        floats: list[float] = []
        for i in range(self.DIM):
            chunk = digest[i * 4 : i * 4 + 4]
            (raw,) = struct.unpack(">I", chunk)
            floats.append(raw / 0xFFFFFFFF)
        return floats

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]
