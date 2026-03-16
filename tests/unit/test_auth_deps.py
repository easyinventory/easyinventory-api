import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.deps import get_current_user


async def test_missing_credentials_raises_401():
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=None)
    assert exc_info.value.status_code == 401
    assert "Missing" in exc_info.value.detail


async def test_invalid_token_raises_401():
    creds = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="bad-token",
    )
    with patch("app.api.deps.verify_token", side_effect=Exception("Invalid")):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=creds)
    assert exc_info.value.status_code == 401
    assert "Invalid" in exc_info.value.detail


async def test_valid_token_returns_claims():
    expected = {"sub": "abc-123", "email": "test@test.com"}
    creds = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="valid-token",
    )
    with patch("app.api.deps.verify_token", return_value=expected):
        claims = await get_current_user(credentials=creds)
    assert claims["sub"] == "abc-123"
    assert claims["email"] == "test@test.com"


async def test_expired_token_raises_401():
    creds = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="expired-token",
    )
    with patch(
        "app.api.deps.verify_token",
        side_effect=Exception("Signature has expired"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=creds)
    assert exc_info.value.status_code == 401
