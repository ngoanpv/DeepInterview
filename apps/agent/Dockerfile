# DeepInterview agent — production image (WP-12).
#
# One image, two run modes:
#
#   API    (default CMD): the FastAPI prep/score service on :8000.
#            uvicorn deepinterview_agent.app:app --host 0.0.0.0 --port 8000
#
#   Worker (override CMD): the LiveKit live voice loop (WP-5). REQUIRES the
#            optional `livekit` extra AND live keys, so it is NOT the default.
#            Build a worker image with the extra, then run the worker module:
#              # add `--extra livekit` to the `uv sync` below (or a worker stage)
#              python -m deepinterview_agent.worker
#            docker-compose.yml runs the worker via the `live` profile.
#
# BUILD CONTEXT = repo root (matches docker-compose.yml `context: .`):
#     docker build -f apps/agent/Dockerfile -t deepinterview-agent .

FROM python:3.11-slim AS base

# uv: fast, reproducible installs from the published binary.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    AGENT_API_PORT=8000

WORKDIR /app

# Copy project metadata first for layer caching, then sources.
COPY apps/agent/pyproject.toml apps/agent/uv.lock ./
COPY apps/agent/src ./src

# Base deps + the lightweight provider SDKs (gemini/openai/supabase/tavily).
# Without them, setting e.g. SUPABASE_URL or LLM_PROVIDER=gemini in .env makes
# the API 500 (ModuleNotFoundError) instead of using the configured provider —
# the image must honor whatever providers the env selects. Still excluded:
# `livekit` (heavy; worker stage below) and `observability` (opt-in tracing).
RUN uv sync --frozen --no-dev --extra gemini --extra openai --extra supabase --extra tavily \
 || uv sync --no-dev --extra gemini --extra openai --extra supabase --extra tavily

EXPOSE 8000

# Default = the API service. Override `command:` to run the worker.
CMD ["uv", "run", "uvicorn", "deepinterview_agent.app:app", "--host", "0.0.0.0", "--port", "8000"]

# ---- worker: base + the `livekit` extra for the live voice loop (WP-5) ------
# The agent-worker compose service (profile: live) builds THIS target — the base
# image omits livekit-agents + the STT/TTS/LLM plugin set the worker imports at
# load time, so running the worker off the base image would ModuleNotFoundError.
FROM base AS worker
RUN uv sync --frozen --no-dev --extra livekit || uv sync --no-dev --extra livekit
# `start` connects to LiveKit and waits for jobs (needs LIVEKIT_*/STT/TTS keys).
CMD ["uv", "run", "python", "-m", "deepinterview_agent.worker", "start"]
