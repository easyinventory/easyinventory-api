"""
testsv2 – real-database test infrastructure.

Fixtures
--------
- ``db``          – per-test async session wrapped in a transaction that is
                    always rolled back (zero cleanup, full isolation).
- ``app``         – FastAPI application wired to use the ``db`` session.
- ``client``      – httpx AsyncClient pointing at the ``app``.

The test database URL is read from the ``DATABASE_URL`` environment variable
(set by the Makefile ``test-v2`` target or CI).  Tables are expected to exist
already (created by ``alembic upgrade head`` before running tests).

A session-scoped ``Base.metadata.create_all`` call is used as a safety net on
top of Alembic migrations.
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
)

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import create_app

# ── Import all models so Base.metadata knows every table ──
import app.models  # noqa: F401

# ── Engine shared across the entire test session ──
test_engine = create_async_engine(settings.DATABASE_URL, echo=False)


# ── Create / drop tables once per session ──
@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    """
    Safety-net: create all tables at session start, drop at end.

    Tables normally exist from ``alembic upgrade head``, but this ensures
    they're present even if migrations haven't been run.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


# ── Transaction-per-test rollback fixture ──
@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a real async session wrapped in a transaction.

    After the test finishes (pass or fail) the transaction is rolled back,
    so every test starts with a clean database and tests can run in any order.
    """
    async with test_engine.connect() as conn:
        transaction = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await transaction.rollback()
            await session.close()


# ── App wired to use the test session ──
@pytest.fixture
def app(db: AsyncSession):
    """Return a FastAPI app that uses the test ``db`` session."""
    application = create_app()

    async def _override_get_db():
        # Mirror production get_db semantics: per-request transaction
        # with commit on success and rollback on error, inside the
        # per-test outer transaction provided by the ``db`` fixture.
        async with db.begin():
            try:
                yield db
            except Exception:
                await db.rollback()
                raise

    application.dependency_overrides[get_db] = _override_get_db
    return application


# ── Async HTTP client ──
@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """httpx AsyncClient wired to the test app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
