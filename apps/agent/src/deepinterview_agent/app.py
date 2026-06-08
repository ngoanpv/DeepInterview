"""FastAPI application factory for the DeepInterview agent API.

Exposes a health check plus the prep and score routers. ``main()`` runs the app
under uvicorn on the configured port.
"""

from __future__ import annotations

from fastapi import FastAPI

from .api import coach as coach_api
from .api import prep as prep_api
from .api import score as score_api
from .api import session as session_api
from .core.config import get_settings


def create_app() -> FastAPI:
    app = FastAPI(title="DeepInterview Agent API")

    @app.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    app.include_router(prep_api.router)
    app.include_router(score_api.router)
    app.include_router(session_api.router)
    app.include_router(coach_api.router)
    return app


app = create_app()


def main() -> None:
    import uvicorn  # noqa: PLC0415

    settings = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.agent_api_port)  # noqa: S104


if __name__ == "__main__":
    main()
