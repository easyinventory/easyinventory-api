"""
testsv2 – real-database test infrastructure.

Fixtures
--------
- ``db``          – per-test async session wrapped in a transaction that is
                    always rolled back (zero cleanup, full isolation).
- ``app``         – FastAPI application wired to use the ``db`` session.
- ``client``      – httpx AsyncClient pointing at the ``app``.

The test database URL is read from the ``DATABASE_URL`` environment variable
(set by the Makefile ``test-v2`` target or CI).  Tables are created once per
session via ``Base.metadata.create_all`` as a safety net on top of Alembic
migrations.
"""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import create_app

# ── Import all models so Base.metadata knows every table ──
import app.models  # noqa: F401

# ── Engine scoped to the entire test session ──
test_engine = create_async_engine(settings.DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Create / drop tables once per session ──
@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    """Create all tables at the start, drop them at the end."""
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
        yield db

    application.dependency_overrides[get_db] = _override_get_db
    return application


# ── Async HTTP client ──
@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """httpx AsyncClient wired to the test app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
