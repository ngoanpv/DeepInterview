# services/lightrag — Knowledge sidecar (WP-8)

The DeepInterview **knowledge service** that powers the Prep Coach. It keeps one
RAG store/graph **per `user_id`** and answers grounded questions with citations.

Runs as a standalone Docker sidecar on **:9621**. This is a self-contained `uv`
project (NOT a node/turbo workspace package): it does not import
`@deepinterview/shared` — the KB wire models are mirrored locally in
`src/lightrag_service/models.py` (snake_case identical to the shared contracts),
so the agent's `HttpKnowledge` client parses responses straight into the shared
`Citation` model.

## Endpoints

| Method | Path         | Body → Response |
| ------ | ------------ | --------------- |
| `GET`  | `/health`    | → `{ "status": "ok", "backend": "naive" }` |
| `POST` | `/kb/ingest` | `KbIngestRequest{ user_id, files[] }` → `KbIngestResponse{ track_id }` |
| `POST` | `/kb/query`  | `KbQueryRequest{ user_id, query, lang }` → `KbQueryResponse{ answer, citations[] }` |

`Citation = { title, url, snippet? }`. `lang` is one of the 10 supported languages
(EN default, multilingual — bge-m3 is cross-lingual).

`/kb/ingest` fetches each `files[]` entry that looks like an `http(s)` URL using
httpx **if it is installed**; when httpx is absent or a fetch fails it treats the
entry as **raw text** (same spirit as the prep CV fallback). So the service is
runnable fully offline with only `fastapi`/`uvicorn`/`pydantic`.

## Backends

The backend is chosen by the `RAG_BACKEND` env var (default `naive`).

### `naive` (default) — `NaiveRAG`

- Dependency-light, **in-memory, deterministic** store. Zero ML deps, no network.
- Ingest splits each doc into ~500-char chunks with source metadata.
- Query scores chunks by lowercased token-overlap (TF), takes the top-3, and
  composes a short extractive `answer` (lead with the best chunk). Each surfaced
  chunk becomes a `Citation` (`title`/`url` = source id, `snippet` = excerpt).
- This is what runs in CI and the default Docker image.

### `lightrag` — `LightRAGBackend` (the real stack)

- The cross-lingual knowledge-graph stack: **LightRAG + RAG-Anything + bge-m3**
  embeddings (and `bge-reranker-v2-m3`). One LightRAG working dir / graph per
  `user_id`; RAG-Anything handles multimodal ingestion (PDF/DOCX/PPTX/images).
- Lazy-imported and **gated**: only constructed when `RAG_BACKEND=lightrag` and
  the optional `rag` extra is installed; otherwise it raises a clear error.
- For citations, use LightRAG's retrieved chunks/sources — the `/query/data`
  response shape exposes the source documents behind an answer, which map cleanly
  onto the `Citation` list returned by `/kb/query`.

## Enabling the real stack

```bash
# Install the heavy extra (lightrag-hku, raganything, sentence-transformers; pulls bge-m3 on first use)
uv sync --extra rag

# Select the backend and run
RAG_BACKEND=lightrag uv run python -m lightrag_service.app
```

bge-m3 (`BAAI/bge-m3`) is downloaded on first use by `sentence-transformers`; set
`LIGHTRAG_WORKING_DIR` to control where per-user graphs are persisted.

## Development

```bash
uv sync                 # naive deps only (fastapi/uvicorn/pydantic + dev)
uv run pytest           # offline tests, no ML deps, no network
uv run ruff check .
uv run python -m lightrag_service.app   # serve on :9621 (env LIGHTRAG_PORT)
```

## Environment

| Var                   | Default         | Purpose |
| --------------------- | --------------- | ------- |
| `RAG_BACKEND`         | `naive`         | Backend select: `naive` or `lightrag`. |
| `LIGHTRAG_PORT`       | `9621`          | Port `main()` / the Docker `CMD` binds. |
| `LIGHTRAG_WORKING_DIR`| `./rag_storage` | (lightrag) where per-user graphs persist. |

> The **agent** calls this service via `LIGHTRAG_URL` (e.g. `http://lightrag:9621`)
> — that variable lives on the agent side, not here.

## Docker

```bash
docker build -t deepinterview-lightrag services/lightrag
docker run -p 9621:9621 deepinterview-lightrag   # NaiveRAG backend
```
