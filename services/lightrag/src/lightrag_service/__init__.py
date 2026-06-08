"""DeepInterview knowledge sidecar (WP-8).

A standalone FastAPI service (Docker, :9621) that powers the Prep Coach. It keeps
one RAG store per ``user_id`` and exposes ``POST /kb/ingest`` and ``POST /kb/query``.

Two backends:

* ``NaiveRAG`` (default) — dependency-light, in-memory, deterministic; runs and
  tests fully offline with ZERO ML deps.
* ``LightRAGBackend`` (``RAG_BACKEND=lightrag``) — the real LightRAG + RAG-Anything
  + bge-m3 stack, lazily imported and gated behind the optional ``rag`` extra.

This package is intentionally standalone: it does NOT import ``@deepinterview/shared``
or the agent's ``shared_models`` — the wire models are mirrored locally in
:mod:`lightrag_service.models` (snake_case identical to the shared contracts).
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.0.0"
