from unittest.mock import patch, MagicMock, AsyncMock
from app.models.user import User


def _mock_user(**overrides):
    """Create a mock User model instance."""
    defaults = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "cognito_sub": "abc-123",
        "email": "test@example.com",
        "system_role": "SYSTEM_USER",
        "is_active": True,
        "created_at": "2026-03-13T00:00:00+00:00",
    }
    defaults.update(overrides)
    mock = MagicMock(spec=User)
    for key, value in defaults.items():
        setattr(mock, key, value)
    return mock


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


async def test_me_returns_200_with_valid_token(client):
    mock_user = _mock_user()
    with patch(
        "app.api.deps.verify_token",
        return_value={"sub": "abc-123", "email": "test@example.com"},
    ):
        with patch("app.api.deps.get_or_create_user", return_value=mock_user):
            response = await client.get(
                "/api/me",
                headers={"Authorization": "Bearer fake-but-mocked-token"},
            )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["system_role"] == "SYSTEM_USER"


async def test_me_returns_user_fields(client):
    mock_user = _mock_user(
        email="admin@company.com",
        system_role="SYSTEM_ADMIN",
    )
    with patch(
        "app.api.deps.verify_token",
        return_value={"sub": "xyz-789", "email": "admin@company.com"},
    ):
        with patch("app.api.deps.get_or_create_user", return_value=mock_user):
            response = await client.get(
                "/api/me",
                headers={"Authorization": "Bearer fake-token"},
            )
    data = response.json()
    assert data["email"] == "admin@company.com"
    assert data["system_role"] == "SYSTEM_ADMIN"
    assert data["is_active"] is True


async def test_health_does_not_require_auth(client):
    """Health check must remain public."""
    response = await client.get("/health")
    assert response.status_code == 200
