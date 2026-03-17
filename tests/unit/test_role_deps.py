import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import HTTPException

from app.api.deps import require_role
from app.models.user import User


def _mock_user(role: str = "SYSTEM_USER") -> MagicMock:
    mock = MagicMock(spec=User)
    mock.system_role = role
    mock.email = "test@test.com"
    return mock


async def test_admin_passes_admin_check():
    """SYSTEM_ADMIN should pass require_role('SYSTEM_ADMIN')."""
    checker = require_role("SYSTEM_ADMIN")
    user = _mock_user(role="SYSTEM_ADMIN")
    result = await checker(current_user=user)
    assert result == user


async def test_regular_user_fails_admin_check():
    """SYSTEM_USER should be rejected by require_role('SYSTEM_ADMIN')."""
    checker = require_role("SYSTEM_ADMIN")
    user = _mock_user(role="SYSTEM_USER")
    with pytest.raises(HTTPException) as exc_info:
        await checker(current_user=user)
    assert exc_info.value.status_code == 403
    assert "Insufficient" in exc_info.value.detail


async def test_multiple_allowed_roles():
    """User with any of the allowed roles should pass."""
    checker = require_role("SYSTEM_ADMIN", "SYSTEM_USER")
    user = _mock_user(role="SYSTEM_USER")
    result = await checker(current_user=user)
    assert result == user


async def test_unknown_role_fails():
    """A role not in the allowed list should be rejected."""
    checker = require_role("SYSTEM_ADMIN")
    user = _mock_user(role="UNKNOWN_ROLE")
    with pytest.raises(HTTPException) as exc_info:
        await checker(current_user=user)
    assert exc_info.value.status_code == 403


async def test_returns_user_on_success():
    """require_role should return the user object, not just pass."""
    checker = require_role("SYSTEM_USER")
    user = _mock_user(role="SYSTEM_USER")
    result = await checker(current_user=user)
    assert result.email == "test@test.com"
