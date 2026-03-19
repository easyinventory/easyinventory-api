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
from sqlalchemy import event
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
test_database_url = settings.DATABASE_URL
if not test_database_url or not str(test_database_url).strip():
    raise RuntimeError(
        "DATABASE_URL must be set to a non-empty test database URL when running tests."
    )
if "test" not in str(test_database_url):
    raise RuntimeError(
        "Refusing to run tests against a non-test database. "
        "Ensure DATABASE_URL points to a dedicated test database (e.g., name contains 'test')."
    )
test_engine = create_async_engine(test_database_url, echo=False)


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

    This uses an outer transaction plus a nested transaction (SAVEPOINT) so
    that ``session.commit()`` calls in application code only release the
    savepoint while the outer transaction remains open and can be rolled
    back at the end of the test.
    """
    async with test_engine.connect() as conn:
        # Begin an outer transaction on the connection.
        outer_transaction = await conn.begin()
        # Create a session bound to this connection.
        session = AsyncSession(bind=conn, expire_on_commit=False)

        # Start a nested transaction (SAVEPOINT) that the session will use.
        nested = await session.begin_nested()

        # When the nested transaction ends (e.g., due to session.commit()),
        # automatically start a new SAVEPOINT as long as the outer
        # transaction is still active.
        @event.listens_for(session.sync_session, "after_transaction_end")
        def _restart_savepoint(sess, transaction) -> None:
            if transaction.nested and not transaction._parent.nested:
                sess.begin_nested()

        try:
            yield session
        finally:
            # Roll back any remaining work and close the session.
            await session.rollback()
            await session.close()
            # Roll back the outer transaction so the database is clean.
            await outer_transaction.rollback()


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
