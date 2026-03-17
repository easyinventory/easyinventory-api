from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.bootstrap import run_bootstrap
from app.core.config import settings
from app.core.database import async_session, engine
from app.api.routes import health, auth, admin, orgs


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
