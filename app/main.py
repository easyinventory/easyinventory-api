import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text

from app.api.routes import admin, auth, health, orgs
from app.core.bootstrap import run_bootstrap
from app.core.config import settings
from app.core.database import async_session, engine
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Verify DB connection and run bootstrap seeder on startup."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    print("[startup] Database connected")

    # Seed bootstrap admin + default org (idempotent)
    async with async_session() as db:
        try:
            await run_bootstrap(db)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            print(f"[bootstrap] ERROR: {exc}")

    yield
    await engine.dispose()
    print("[shutdown] Database disconnected")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── Exception handler for domain errors ──
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    # ── Catch-all for unhandled exceptions ──
    # IMPORTANT: this must be registered *before* add_middleware(CORSMiddleware).
    # Starlette's build_middleware_stack puts middlewares in reverse-add order, so
    # the last-added middleware is outermost.  By registering this catch-all first
    # and CORSMiddleware second, the stack becomes:
    #   ServerErrorMiddleware → CORSMiddleware → catch_all → ExceptionMiddleware → router
    # Every response — including 500s — therefore flows through CORSMiddleware and
    # always carries the correct Access-Control-Allow-Origin header.
    # (Using @app.exception_handler(Exception) instead would send the handler to
    # ServerErrorMiddleware, which is *outside* CORSMiddleware.)
    @app.middleware("http")
    async def catch_unhandled_exceptions(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            logger.exception("Unhandled exception: %s", exc)
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(orgs.router)

    return app


app = create_app()
