"""FastAPI application and recoverable PostgreSQL-backed maintenance loops."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from twitch_games import __version__
from twitch_games.auth import Auth
from twitch_games.auth import router as auth_router
from twitch_games.config import Settings
from twitch_games.contracts.models import ErrorEnvelope
from twitch_games.database import Database
from twitch_games.errors import GameError
from twitch_games.game_service import GameService
from twitch_games.http_auth import HTTPAuth
from twitch_games.http_game_service import HTTPGameService
from twitch_games.http_publisher import HTTPPublisher
from twitch_games.routes import router as game_router
from twitch_games.supabase_http import SupabaseHTTP
from twitch_games.synchronization import Publisher

logger = logging.getLogger(__name__)


async def maintenance(operation, interval):
    while True:
        try:
            await asyncio.shield(work := asyncio.create_task(asyncio.to_thread(operation)))
        except asyncio.CancelledError:
            await work
            raise
        except Exception as error:
            # SQL/HTTP exception strings may contain parameters or credentials.
            logger.warning("Maintenance operation failed (%s)", type(error).__name__)
        await asyncio.sleep(interval)


class BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > 512 * 1024:
                return await JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "payload_too_large",
                            "message": "Request body exceeds 512 KiB",
                        }
                    },
                )(scope, receive, send)
            chunks.append(message)
            if not message.get("more_body", False):
                break
        index = 0

        async def replay():
            nonlocal index
            if index < len(chunks):
                message = chunks[index]
                index += 1
                return message
            return await receive()

        await self.app(scope, replay, send)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(app):
        http_storage = settings.storage_backend == "supabase_http"
        database = (
            (
                SupabaseHTTP(settings)
                if settings.supabase_url and settings.supabase_secret_key
                else None
            )
            if http_storage
            else (Database(settings) if settings.database_url else None)
        )
        app.state.database = database
        auth = app.state.auth = (HTTPAuth if http_storage else Auth)(settings, database)
        service = app.state.game_service = (HTTPGameService if http_storage else GameService)(
            database, auth
        )
        publisher = app.state.publisher = (HTTPPublisher if http_storage else Publisher)(
            database, auth
        )
        tasks = []
        app.state.runtime_ready = False

        async def start_workers():
            if settings.oauth_configured:
                await asyncio.to_thread(auth.maintenance, True)
            if getattr(auth, "stopping", False):
                return
            tasks.extend(
                [
                    asyncio.create_task(maintenance(service.close_due, 0.25)),
                    asyncio.create_task(maintenance(publisher.publish_one, 0.25)),
                    asyncio.create_task(maintenance(auth.maintenance, 60)),
                ]
            )
            if hasattr(service, "generate_due"):
                tasks.append(asyncio.create_task(maintenance(service.generate_due, 1)))
            app.state.runtime_ready = True

        async def await_database():
            while not getattr(auth, "stopping", False):
                work = asyncio.create_task(asyncio.to_thread(database.status))
                try:
                    status = await asyncio.shield(work)
                except asyncio.CancelledError:
                    await work
                    raise
                if status == "ok":
                    work = asyncio.create_task(start_workers())
                    try:
                        await asyncio.shield(work)
                    except asyncio.CancelledError:
                        await work
                        raise
                    except (GameError, SQLAlchemyError) as error:
                        logger.warning("Runtime startup retry (%s)", type(error).__name__)
                        await asyncio.sleep(3)
                        continue
                    return
                await asyncio.sleep(3)

        if database:
            if await asyncio.to_thread(database.status) == "ok":
                await start_workers()
            else:
                tasks.append(asyncio.create_task(await_database()))
        try:
            yield
        finally:
            auth.stopping = True
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            # Synchronous operations have bounded timeouts and may finish after cancellation.
            # HTTPX closes pooled connections on process shutdown as well.
            auth.provider.client.close()
            if database:
                database.close()

    app = FastAPI(
        title="Twitch Games Backend",
        version=__version__,
        description="Authenticated quote game API with conditional stream captions.",
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.add_middleware(BodyLimit)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-CSRF-Token"],
        )
    app.include_router(auth_router)
    app.include_router(game_router)

    @app.middleware("http")
    async def private_responses(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(GameError)
    async def game_error(request, error):
        return JSONResponse(
            status_code=error.status,
            content={"error": {"code": error.code, "message": error.message}},
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, error):
        logger.warning("Database request failed (%s)", type(error).__name__)
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "database_unavailable",
                    "message": "Database operation unavailable; retry shortly",
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request fields are missing or invalid",
                }
            },
        )

    @app.get("/health/live", tags=["health"])
    def liveness():
        return {"status": "ok", "service": "twitch-games-backend", "version": __version__}

    @app.get(
        "/health/ready",
        tags=["health"],
        responses={503: {"description": "Dependency configuration unavailable"}},
    )
    def readiness(request: Request):
        database = request.app.state.database
        db_status = database.status() if database else "not_configured"
        auth_ready = settings.oauth_configured and settings.extension_configured
        notifications = request.app.state.publisher.configured
        ready = (
            db_status == "ok" and auth_ready and notifications and request.app.state.runtime_ready
        )
        return JSONResponse(
            status_code=200 if ready else 503,
            content={
                "status": "ready" if ready else "not_ready",
                "stage": "gameplay",
                "dependencies": {
                    "database": db_status,
                    "twitch_auth": "configured" if auth_ready else "not_configured",
                    "gameplay": "implemented",
                    "notifications": "configured" if notifications else "not_configured",
                },
            },
        )

    original_openapi = app.openapi

    def openapi():
        schema = original_openapi()
        schema.setdefault("components", {}).setdefault("securitySchemes", {}).update(
            {
                "ExtensionJWT": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "Twitch Extension JWT",
                },
                "DashboardSession": {
                    "type": "apiKey",
                    "in": "cookie",
                    "name": "twitch_games_session",
                },
            }
        )
        error_schema = ErrorEnvelope.model_json_schema(ref_template="#/components/schemas/{model}")
        schema["components"].setdefault("schemas", {}).update(error_schema.pop("$defs", {}))
        schema["components"]["schemas"]["ErrorEnvelope"] = error_schema
        for path, methods in schema["paths"].items():
            if path.startswith("/api/v1/") and path not in {
                "/api/v1/auth/twitch",
                "/api/v1/auth/twitch/callback",
            }:
                for operation in methods.values():
                    operation["security"] = [{"ExtensionJWT": []}, {"DashboardSession": []}]
                    for status in ("401", "403", "409", "422", "503"):
                        operation["responses"][status] = {
                            "description": "Application error",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorEnvelope"}
                                }
                            },
                        }
        return schema

    app.openapi = openapi
    return app
