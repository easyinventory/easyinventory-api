import pytest
from httpx import AsyncClient, ASGITransport

from app.main import create_app


@pytest.fixture
def app():
    """Create a fresh app instance for each test."""
    return create_app()


@pytest.fixture
async def client(app):
    """Async HTTP client that talks directly to the app (no network).

    raise_app_exceptions=False mirrors real ASGI server behaviour: when the
    app has already sent a response (e.g. a 500 JSON body) and *then*
    re-raises the exception (Starlette always does this so uvicorn can log
    it), httpx returns the response rather than propagating the exception to
    the test.  Without this flag, unhandled-exception tests would fail with
    the raw exception instead of letting us assert on status code / headers.
    """
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
