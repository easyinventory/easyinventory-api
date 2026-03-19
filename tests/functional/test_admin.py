from unittest.mock import patch, MagicMock
from app.models.user import User


def _mock_user(**overrides):
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


async def test_admin_endpoint_returns_403_for_regular_user(client):
    mock_user = _mock_user(system_role="SYSTEM_USER")
    with patch(
        "app.auth.deps.verify_token",
        return_value={"sub": "abc-123", "email": "test@example.com"},
    ):
        with patch("app.auth.deps.get_or_create_user", return_value=mock_user):
            response = await client.get(
                "/api/admin/status",
                headers={"Authorization": "Bearer fake-token"},
            )
    assert response.status_code == 403


async def test_admin_endpoint_returns_200_for_admin(client):
    mock_user = _mock_user(
        system_role="SYSTEM_ADMIN",
        email="admin@company.com",
    )
    with patch(
        "app.auth.deps.verify_token",
        return_value={"sub": "admin-sub", "email": "admin@company.com"},
    ):
        with patch("app.auth.deps.get_or_create_user", return_value=mock_user):
            response = await client.get(
                "/api/admin/status",
                headers={"Authorization": "Bearer fake-token"},
            )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "SYSTEM_ADMIN"
    assert data["email"] == "admin@company.com"


async def test_admin_endpoint_returns_401_without_token(client):
    response = await client.get("/api/admin/status")
    assert response.status_code == 401


async def test_admin_endpoint_returns_403_detail(client):
    mock_user = _mock_user(system_role="SYSTEM_USER")
    with patch(
        "app.auth.deps.verify_token",
        return_value={"sub": "abc-123", "email": "test@example.com"},
    ):
        with patch("app.auth.deps.get_or_create_user", return_value=mock_user):
            response = await client.get(
                "/api/admin/status",
                headers={"Authorization": "Bearer fake-token"},
            )
    data = response.json()
    assert "Insufficient" in data["detail"]
