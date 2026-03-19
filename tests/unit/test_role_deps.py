import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import HTTPException

from app.auth.deps import RequireRole
from app.core.roles import SystemRole
from app.models.user import User


def _mock_user(role: str = SystemRole.USER) -> MagicMock:
    mock = MagicMock(spec=User)
    mock.system_role = role
    mock.email = "test@test.com"
    return mock


async def test_admin_passes_admin_check():
    """SYSTEM_ADMIN should pass RequireRole('SYSTEM_ADMIN')."""
    checker = RequireRole(SystemRole.ADMIN)
    user = _mock_user(role=SystemRole.ADMIN)
    result = await checker(current_user=user)
    assert result == user


async def test_regular_user_fails_admin_check():
    """SYSTEM_USER should be rejected by RequireRole('SYSTEM_ADMIN')."""
    checker = RequireRole(SystemRole.ADMIN)
    user = _mock_user(role=SystemRole.USER)
    with pytest.raises(HTTPException) as exc_info:
        await checker(current_user=user)
    assert exc_info.value.status_code == 403
    assert "Insufficient" in exc_info.value.detail


async def test_multiple_allowed_roles():
    """User with any of the allowed roles should pass."""
    checker = RequireRole(SystemRole.ADMIN, SystemRole.USER)
    user = _mock_user(role=SystemRole.USER)
    result = await checker(current_user=user)
    assert result == user


async def test_unknown_role_fails():
    """A role not in the allowed list should be rejected."""
    checker = RequireRole(SystemRole.ADMIN)
    user = _mock_user(role="UNKNOWN_ROLE")
    with pytest.raises(HTTPException) as exc_info:
        await checker(current_user=user)
    assert exc_info.value.status_code == 403


async def test_returns_user_on_success():
    """RequireRole should return the user object, not just pass."""
    checker = RequireRole(SystemRole.USER)
    user = _mock_user(role=SystemRole.USER)
    result = await checker(current_user=user)
    assert result.email == "test@test.com"
