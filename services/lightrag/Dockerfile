# DeepInterview knowledge sidecar (WP-8) — FastAPI RAG service on :9621.
#
# Default build installs the NaiveRAG backend only (fastapi/uvicorn/pydantic) so the
# image is small and runs fully offline. To ship the real LightRAG + RAG-Anything +
# bge-m3 stack, add `--extra rag` to the `uv sync` below and set RAG_BACKEND=lightrag.
FROM python:3.11-slim

# uv: fast, reproducible installs from the copied binary.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy project metadata first for better layer caching, then sources.
COPY pyproject.toml ./
COPY src ./src
COPY README.md ./

# Install the naive (default) dependencies only — no heavy ML deps.
RUN uv sync --no-dev

ENV LIGHTRAG_PORT=9621
ENV RAG_BACKEND=naive

EXPOSE 9621

# Run the FastAPI app via the package entrypoint (reads $LIGHTRAG_PORT).
CMD ["uv", "run", "python", "-m", "lightrag_service.app"]
