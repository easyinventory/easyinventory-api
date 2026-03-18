import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.deps import get_current_org_membership, get_current_user
from app.models.org_membership import OrgMembership
from app.models.user import User


async def test_missing_credentials_raises_401():
    mock_db = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=None, db=mock_db)
    assert exc_info.value.status_code == 401
    assert "Missing" in exc_info.value.detail


async def test_invalid_token_raises_401():
    mock_db = AsyncMock()
    creds = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="bad-token",
    )
    with patch("app.api.deps.verify_token", side_effect=Exception("Invalid")):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=creds, db=mock_db)
    assert exc_info.value.status_code == 401


async def test_valid_token_returns_user():
    mock_user = MagicMock(spec=User)
    mock_user.cognito_sub = "abc-123"
    mock_user.email = "test@test.com"

    mock_db = AsyncMock()
    creds = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="valid-token",
    )
    with patch(
        "app.api.deps.verify_token",
        return_value={"sub": "abc-123", "email": "test@test.com"},
    ):
        with patch("app.api.deps.get_or_create_user", return_value=mock_user):
            user = await get_current_user(credentials=creds, db=mock_db)
    assert user.cognito_sub == "abc-123"
    assert user.email == "test@test.com"


async def test_expired_token_raises_401():
    mock_db = AsyncMock()
    creds = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="expired-token",
    )
    with patch(
        "app.api.deps.verify_token",
        side_effect=Exception("Signature has expired"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=creds, db=mock_db)
    assert exc_info.value.status_code == 401


async def test_get_current_org_membership_returns_first_active_membership():
    mock_user = MagicMock(spec=User)
    mock_user.id = "user-1"

    mock_membership = MagicMock(spec=OrgMembership)

    mock_scalars = MagicMock()
    mock_scalars.first.return_value = mock_membership

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    membership = await get_current_org_membership(
        current_user=mock_user, db=mock_db, x_org_id=None,
    )

    assert membership is mock_membership
    mock_db.execute.assert_awaited_once()


async def test_get_current_org_membership_raises_403_when_missing():
    mock_user = MagicMock(spec=User)
    mock_user.id = "user-1"

    mock_scalars = MagicMock()
    mock_scalars.first.return_value = None

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    with pytest.raises(HTTPException) as exc_info:
        await get_current_org_membership(
            current_user=mock_user, db=mock_db, x_org_id=None,
        )

    assert exc_info.value.status_code == 403
    assert "No active organization membership" in exc_info.value.detail
