"""Application factory: only truthful foundation routes are mounted in Step 1."""

from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from twitch_games import __version__
from twitch_games.config import Settings
from twitch_games.database import Database, DatabaseStatus


class Liveness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    service: Literal["twitch-games-backend"] = "twitch-games-backend"
    version: str = __version__


class PersistenceDependencies(BaseModel):
    database: DatabaseStatus
    twitch_auth: Literal["not_implemented"] = "not_implemented"
    gameplay: Literal["not_implemented"] = "not_implemented"


class Readiness(BaseModel):
    status: Literal["not_ready"] = "not_ready"
    stage: Literal["persistence"] = "persistence"
    dependencies: PersistenceDependencies


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database = Database(settings) if settings.database_url is not None else None
        app.state.database = database
        try:
            yield
        finally:
            if database is not None:
                database.close()

    app = FastAPI(
        title="Twitch Games Backend",
        version=__version__,
        description=(
            "Step 2 persistence foundation. Authentication and game routes are not implemented. "
            "The separate contract under backend/docs is a frontend handoff, not a live API."
        ),
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        )

    @app.get("/health/live", response_model=Liveness, tags=["health"])
    def liveness(response: Response) -> Liveness:
        response.headers["Cache-Control"] = "no-store"
        return Liveness()

    @app.get(
        "/health/ready",
        status_code=503,
        responses={503: {"model": Readiness, "description": "Game integrations not implemented"}},
        response_model=None,
        tags=["health"],
    )
    def readiness() -> JSONResponse:
        database = app.state.database
        database_status = database.status() if database is not None else "not_configured"
        return JSONResponse(
            status_code=503,
            content=Readiness(
                dependencies=PersistenceDependencies(database=database_status)
            ).model_dump(mode="json"),
            headers={"Cache-Control": "no-store"},
        )

    return app
