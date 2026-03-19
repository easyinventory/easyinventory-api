from unittest.mock import patch, MagicMock, AsyncMock
from app.core.database import get_db
from app.models.user import User
from app.models.org_membership import OrgMembership
from app.models.organization import Organization


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


async def test_orgs_me_returns_401_without_token(client):
    response = await client.get("/api/orgs/me")
    assert response.status_code == 401


async def test_orgs_me_returns_empty_list_for_no_memberships(app, client):
    mock_user = _mock_user()

    # Mock the DB query to return empty results
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        with patch(
            "app.auth.deps.verify_token",
            return_value={"sub": "abc-123", "email": "test@example.com"},
        ):
            with patch("app.auth.deps.get_or_create_user", return_value=mock_user):
                response = await client.get(
                    "/api/orgs/me",
                    headers={"Authorization": "Bearer fake-token"},
                )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json() == []


async def test_orgs_me_returns_memberships(app, client):
    mock_user = _mock_user(system_role="SYSTEM_ADMIN")

    mock_org = MagicMock(spec=Organization)
    mock_org.id = "660e8400-e29b-41d4-a716-446655440000"
    mock_org.name = "Default Organization"
    mock_org.created_at = "2026-03-13T00:00:00+00:00"

    mock_membership = MagicMock(spec=OrgMembership)
    mock_membership.id = "770e8400-e29b-41d4-a716-446655440000"
    mock_membership.org_id = mock_org.id
    mock_membership.org_role = "ORG_OWNER"
    mock_membership.is_active = True
    mock_membership.joined_at = "2026-03-13T00:00:00+00:00"
    mock_membership.organization = mock_org

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_membership]

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        with patch(
            "app.auth.deps.verify_token",
            return_value={"sub": "admin-sub", "email": "admin@company.com"},
        ):
            with patch("app.auth.deps.get_or_create_user", return_value=mock_user):
                response = await client.get(
                    "/api/orgs/me",
                    headers={"Authorization": "Bearer fake-token"},
                )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["org_role"] == "ORG_OWNER"
    assert data[0]["organization"]["name"] == "Default Organization"
