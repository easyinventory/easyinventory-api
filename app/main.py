import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.bootstrap.seeder import run_bootstrap
from app.core.config import settings
from app.core.database import async_session, engine
from app.core.exceptions import AppError
from app.core.middleware import JsonFormatter, RequestLoggingMiddleware
from app.auth.routes import router as auth_router
from app.orgs.routes import router as orgs_router
from app.admin.routes_orgs import router as admin_orgs_router
from app.admin.routes_users import router as admin_users_router
from app.health.routes import router as health_router
from app.products.routes import router as products_router
from app.suppliers.routes import router as suppliers_router

# ── Structured JSON logging to stdout → Docker → CloudWatch ──
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Verify DB connection and run bootstrap seeder on startup."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("Database connected")

    # Seed bootstrap admin + default org (idempotent)
    async with async_session() as db:
        try:
            await run_bootstrap(db)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.error("Bootstrap failed: %s", exc)

    yield
    await engine.dispose()
    logger.info("Database disconnected")


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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(admin_orgs_router)
    app.include_router(admin_users_router)
    app.include_router(orgs_router)
    app.include_router(suppliers_router)
    app.include_router(products_router)

    return app


app = create_app()
