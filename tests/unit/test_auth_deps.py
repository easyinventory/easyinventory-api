import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.deps import get_current_user
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
