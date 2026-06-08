"""Local Pydantic mirror of the shared KB wire contracts.

This service is standalone (it cannot import ``@deepinterview/shared`` or the
agent's ``shared_models``), so the request/response shapes are redefined here.
They are snake_case identical to ``packages/shared`` and the agent's mirror, so
the agent's ``HttpKnowledge`` client can parse responses straight into the shared
``Citation`` model.

Languages mirror ``packages/shared`` (EN default, multilingual).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

Language = Literal["en", "vi", "es", "zh", "hi", "id", "pt", "fr", "de", "ja"]


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    url: str
    snippet: str | None = None


class KbIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str
    files: list[str]


class KbIngestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_id: str


class KbQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str
    query: str
    lang: Language


class KbQueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str
    citations: list[Citation]
