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

# Dependency layers FIRST (lockfiles only, --no-install-project), source LAST:
# deps and the baked ML models stay cached across code edits — previously any
# one-line src change re-downloaded the turn-detector weights (minutes).
COPY apps/agent/pyproject.toml apps/agent/uv.lock ./

# Base deps + the lightweight provider SDKs (gemini/openai/supabase/tavily).
# Without them, setting e.g. SUPABASE_URL or LLM_PROVIDER=gemini in .env makes
# the API 500 (ModuleNotFoundError) instead of using the configured provider —
# the image must honor whatever providers the env selects. Still excluded:
# `livekit` (heavy; worker stages below) and `observability` (opt-in tracing).
RUN uv sync --frozen --no-dev --no-install-project --extra gemini --extra openai --extra supabase --extra tavily \
 || uv sync --no-dev --no-install-project --extra gemini --extra openai --extra supabase --extra tavily

# ---- worker-deps: + the `livekit` extra and baked model weights (no src) ----
# Branches BEFORE the source copy so the heavy plugin install and the
# turn-detector/Silero model downloads are cache-stable across code changes.
FROM base AS worker-deps
RUN uv sync --frozen --no-dev --no-install-project --extra livekit --extra gemini --extra openai --extra supabase --extra tavily \
 || uv sync --no-dev --no-install-project --extra livekit --extra gemini --extra openai --extra supabase --extra tavily
# Bake the semantic turn-detector model weights (and Silero VAD) into the
# image: importing each plugin registers it, download_files() fetches its
# model. Without this the FIRST live session stalls on a runtime download.
RUN .venv/bin/python -c "import livekit.plugins.silero, livekit.plugins.turn_detector; \
from livekit.agents.plugin import Plugin; \
[p.download_files() for p in Plugin.registered_plugins]"

# ---- api: deps + source (compose `agent-api` builds target: api) ------------
FROM base AS api
COPY apps/agent/src ./src
RUN uv sync --frozen --no-dev --extra gemini --extra openai --extra supabase --extra tavily \
 || uv sync --no-dev --extra gemini --extra openai --extra supabase --extra tavily

EXPOSE 8000

# Default = the API service. Override `command:` to run the worker.
CMD ["uv", "run", "uvicorn", "deepinterview_agent.app:app", "--host", "0.0.0.0", "--port", "8000"]

# ---- worker: worker-deps + source (compose `agent-worker`, profile: live) ---
# The api image omits livekit-agents + the STT/TTS/LLM plugin set the worker
# imports at load time, so running the worker off the api image would
# ModuleNotFoundError.
FROM worker-deps AS worker
COPY apps/agent/src ./src
RUN uv sync --frozen --no-dev --extra livekit --extra gemini --extra openai --extra supabase --extra tavily \
 || uv sync --no-dev --extra livekit --extra gemini --extra openai --extra supabase --extra tavily
# `start` connects to LiveKit and waits for jobs (needs LIVEKIT_*/STT/TTS keys).
CMD ["uv", "run", "python", "-m", "deepinterview_agent.worker", "start"]
