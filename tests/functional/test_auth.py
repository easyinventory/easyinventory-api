import pytest
from unittest.mock import patch, AsyncMock, MagicMock


async def test_me_returns_401_without_token(client):
    response = await client.get("/api/me")
    assert response.status_code == 401


async def test_me_returns_401_with_invalid_token(client):
    response = await client.get(
        "/api/me",
        headers={"Authorization": "Bearer garbage.token.here"},
    )
    assert response.status_code == 401


async def test_me_returns_401_detail_message(client):
    response = await client.get("/api/me")
    data = response.json()
    assert "detail" in data


async def test_me_returns_www_authenticate_header(client):
    response = await client.get("/api/me")
    assert response.headers.get("www-authenticate") == "Bearer"


def _mock_verify_token(claims: dict):
    """Create a mock that replaces verify_token with static claims."""

    def _verify(token: str) -> dict:
        return claims

    return _verify


async def test_me_returns_200_with_valid_token(client):
    mock_claims = {
        "sub": "abc-123",
        "email": "test@example.com",
        "token_use": "id",
    }
    with patch(
        "app.api.deps.verify_token",
        side_effect=_mock_verify_token(mock_claims),
    ):
        response = await client.get(
            "/api/me",
            headers={"Authorization": "Bearer fake-but-mocked-token"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["sub"] == "abc-123"
    assert data["email"] == "test@example.com"


async def test_me_returns_correct_claims(client):
    mock_claims = {
        "sub": "user-789",
        "email": "admin@company.com",
        "token_use": "id",
    }
    with patch(
        "app.api.deps.verify_token",
        side_effect=_mock_verify_token(mock_claims),
    ):
        response = await client.get(
            "/api/me",
            headers={"Authorization": "Bearer fake-but-mocked-token"},
        )
    data = response.json()
    assert data["sub"] == "user-789"
    assert data["email"] == "admin@company.com"
    assert data["token_use"] == "id"


async def test_health_does_not_require_auth(client):
    """Health check must remain public — no auth needed."""
    response = await client.get("/health")
    assert response.status_code == 200
