"""
Functional tests for CORS header behaviour.

Key regression tested here:
  Before the fix, any unhandled exception (e.g. a Cognito ClientError on POST
  /api/admin/orgs) was caught by ServerErrorMiddleware — which sits *outside*
  CORSMiddleware — so the 500 response carried no Access-Control-Allow-Origin
  header and the browser reported a "CORS error" instead of the real 500.

The fix adds a catch-all Exception handler registered via @app.exception_handler,
which is processed by ExceptionMiddleware *inside* CORSMiddleware.  Every response
— including 500s — therefore always carries the correct CORS headers.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.core.database import get_db
from app.models.user import User

# The default CORS_ORIGINS setting includes this origin.
ALLOWED_ORIGIN = "http://localhost:5173"
BLOCKED_ORIGIN = "https://evil.example.com"


# ── helpers ────────────────────────────────────────────────────────────────────


def _mock_admin() -> MagicMock:
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.email = "admin@test.com"
    user.system_role = "SYSTEM_ADMIN"
    user.is_active = True
    return user


def _mock_db() -> MagicMock:
    db = MagicMock()

    def _add(instance: object) -> None:
        if getattr(instance, "id", None) is None:
            instance.id = uuid.uuid4()  # type: ignore[union-attr]
        if getattr(instance, "created_at", None) is None:
            instance.created_at = datetime.now(timezone.utc)  # type: ignore[union-attr]

    db.add = MagicMock(side_effect=_add)
    db.flush = AsyncMock()
    return db


def _cognito_client_error() -> ClientError:
    """Simulate an unexpected Cognito error (e.g. throttle / service error)."""
    return ClientError(
        error_response={
            "Error": {"Code": "TooManyRequestsException", "Message": "Rate exceeded"}
        },
        operation_name="AdminCreateUser",
    )


# ── preflight ──────────────────────────────────────────────────────────────────


async def test_preflight_allowed_origin(client) -> None:
    """OPTIONS preflight from an allowed origin must return 200 with CORS headers."""
    response = await client.options(
        "/api/admin/orgs",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


async def test_preflight_blocked_origin(client) -> None:
    """OPTIONS preflight from an unknown origin must NOT echo back allow-origin."""
    response = await client.options(
        "/api/admin/orgs",
        headers={
            "Origin": BLOCKED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.headers.get("access-control-allow-origin") != BLOCKED_ORIGIN


# ── successful request ─────────────────────────────────────────────────────────


async def test_cors_header_on_successful_get(app, client) -> None:
    """A normal 200 GET response must carry the CORS allow-origin header."""
    admin = _mock_admin()
    db = _mock_db()

    app.dependency_overrides[get_db] = lambda: db
    try:
        with (
            patch(
                "app.api.deps.verify_token",
                return_value={"sub": "x", "email": admin.email},
            ),
            patch("app.api.deps.get_or_create_user", return_value=admin),
            patch("app.services.org_service.list_all_orgs", return_value=[]),
        ):
            response = await client.get(
                "/api/admin/orgs",
                headers={
                    "Authorization": "Bearer fake",
                    "Origin": ALLOWED_ORIGIN,
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


# ── regression: 500 must still carry CORS headers ─────────────────────────────


async def test_cors_header_present_on_500(app, client) -> None:
    """
    Regression test for the CORS-on-500 bug.

    When invite_cognito_user raises an unhandled ClientError the API must
    still return Access-Control-Allow-Origin so the browser sees a 500
    rather than a misleading "CORS error".
    """
    admin = _mock_admin()
    db = _mock_db()

    app.dependency_overrides[get_db] = lambda: db
    try:
        with (
            patch(
                "app.api.deps.verify_token",
                return_value={"sub": "x", "email": admin.email},
            ),
            patch("app.api.deps.get_or_create_user", return_value=admin),
            patch(
                "app.services.invite_service.org_service.find_user_by_email",
                return_value=None,
            ),
            # Simulate Cognito throwing an unexpected error
            patch(
                "app.services.invite_service.invite_cognito_user",
                side_effect=_cognito_client_error(),
            ),
        ):
            response = await client.post(
                "/api/admin/orgs",
                json={"name": "Test Org", "owner_email": "new@test.com"},
                headers={
                    "Authorization": "Bearer fake",
                    "Origin": ALLOWED_ORIGIN,
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    # The response must be a 500 (not masked as a CORS error)
    assert response.status_code == 500
    # And CORS headers must still be present
    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


async def test_no_cors_header_on_500_from_blocked_origin(app, client) -> None:
    """
    A 500 from an origin that isn't in CORS_ORIGINS should still NOT
    echo back access-control-allow-origin.
    """
    admin = _mock_admin()
    db = _mock_db()

    app.dependency_overrides[get_db] = lambda: db
    try:
        with (
            patch(
                "app.api.deps.verify_token",
                return_value={"sub": "x", "email": admin.email},
            ),
            patch("app.api.deps.get_or_create_user", return_value=admin),
            patch(
                "app.services.invite_service.org_service.find_user_by_email",
                return_value=None,
            ),
            patch(
                "app.services.invite_service.invite_cognito_user",
                side_effect=_cognito_client_error(),
            ),
        ):
            response = await client.post(
                "/api/admin/orgs",
                json={"name": "Test Org", "owner_email": "new@test.com"},
                headers={
                    "Authorization": "Bearer fake",
                    "Origin": BLOCKED_ORIGIN,
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 500
    assert response.headers.get("access-control-allow-origin") != BLOCKED_ORIGIN
