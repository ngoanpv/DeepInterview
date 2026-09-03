# DeepInterview knowledge sidecar (WP-8) — FastAPI RAG service on :9621.
#
# Default build installs the NaiveRAG backend only (fastapi/uvicorn/pydantic) so the
# image is small and runs fully offline. To ship the real LightRAG + RAG-Anything +
# bge-m3 stack, add `--extra rag` to the `uv sync` below and set RAG_BACKEND=lightrag.
FROM python:3.14-slim

# uv: fast, reproducible installs from the copied binary. Pin the tag so a
# breaking uv release can't silently change the image.
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/

WORKDIR /app

# Copy project metadata + lockfile first for better layer caching, then sources.
# The lockfile MUST be copied for `--frozen` to reproduce the resolved set
# instead of re-resolving on every build.
COPY pyproject.toml uv.lock ./
COPY src ./src
COPY README.md ./

# Install the naive (default) dependencies only — no heavy ML deps. `--frozen`
# fails loudly if uv.lock has drifted from pyproject rather than silently
# resolving a different set.
RUN uv sync --frozen --no-dev

ENV LIGHTRAG_PORT=9621 \
    RAG_BACKEND=naive

EXPOSE 9621

# Drop root: run as an unprivileged user. The venv is already built, so we invoke
# its interpreter directly (no `uv run` at runtime → nothing to write).
RUN useradd --create-home --uid 10001 appuser \
 && chown -R appuser:appuser /app
USER appuser

# Run the FastAPI app via the package entrypoint (reads $LIGHTRAG_PORT).
CMD [".venv/bin/python", "-m", "lightrag_service.app"]
