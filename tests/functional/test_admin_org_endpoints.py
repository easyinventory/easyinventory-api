import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.database import get_db
from app.models.user import User


def _mock_admin():
    mock = MagicMock(spec=User)
    mock.id = uuid.uuid4()
    mock.email = "admin@test.com"
    mock.system_role = "SYSTEM_ADMIN"
    mock.is_active = True
    return mock


def _mock_regular_user():
    mock = MagicMock(spec=User)
    mock.id = uuid.uuid4()
    mock.email = "user@test.com"
    mock.system_role = "SYSTEM_USER"
    mock.is_active = True
    return mock


@contextmanager
def _db_override(app, mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)


def _mock_db_session():
    mock_db = MagicMock()

    def _add(instance):
        if getattr(instance, "id", None) is None:
            instance.id = uuid.uuid4()
        if getattr(instance, "created_at", None) is None:
            instance.created_at = datetime.now(timezone.utc)

    mock_db.add = MagicMock(side_effect=_add)
    mock_db.flush = AsyncMock()
    return mock_db


async def test_non_admin_cannot_create_org(client):
    """SYSTEM_USER should get 403."""
    user = _mock_regular_user()

    with patch(
        "app.auth.deps.verify_token", return_value={"sub": "abc", "email": user.email}
    ):
        with patch("app.auth.deps.get_or_create_user", return_value=user):
            response = await client.post(
                "/api/admin/orgs",
                json={"name": "New Org", "owner_email": "owner@test.com"},
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 403


async def test_create_org_returns_401_without_token(client):
    response = await client.post(
        "/api/admin/orgs",
        json={"name": "Test", "owner_email": "test@test.com"},
    )
    assert response.status_code == 401


async def test_list_orgs_returns_403_for_non_admin(client):
    user = _mock_regular_user()
    with patch(
        "app.auth.deps.verify_token", return_value={"sub": "abc", "email": user.email}
    ):
        with patch("app.auth.deps.get_or_create_user", return_value=user):
            response = await client.get(
                "/api/admin/orgs",
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 403


async def test_admin_can_delete_user_system_and_cognito(client):
    admin = _mock_admin()
    target = MagicMock(spec=User)
    target.id = uuid.uuid4()
    target.email = "delete.me@test.com"
    target.cognito_sub = "sub-delete-me"

    with patch(
        "app.auth.deps.verify_token",
        return_value={"sub": "abc", "email": admin.email},
    ):
        with patch("app.auth.deps.get_or_create_user", return_value=admin):
            with patch("app.users.service.get_user_by_id", return_value=target):
                with patch(
                    "app.admin.routes_users.user_service.delete_user_completely",
                    new_callable=AsyncMock,
                ) as mock_delete_db:
                    with patch(
                        "app.admin.routes_users.delete_cognito_user"
                    ) as mock_delete_cognito:
                        response = await client.delete(
                            f"/api/admin/users/{target.id}",
                            headers={"Authorization": "Bearer fake"},
                        )

    assert response.status_code == 204
    mock_delete_db.assert_awaited_once()
    mock_delete_cognito.assert_called_once_with(target.email, target.cognito_sub)


async def test_admin_delete_user_returns_404_for_missing_user(client):
    admin = _mock_admin()
    missing_id = uuid.uuid4()

    with patch(
        "app.auth.deps.verify_token",
        return_value={"sub": "abc", "email": admin.email},
    ):
        with patch("app.auth.deps.get_or_create_user", return_value=admin):
            with patch("app.users.service.get_user_by_id", return_value=None):
                response = await client.delete(
                    f"/api/admin/users/{missing_id}",
                    headers={"Authorization": "Bearer fake"},
                )

    assert response.status_code == 404


async def test_admin_cannot_delete_own_account(client):
    admin = _mock_admin()

    with patch(
        "app.auth.deps.verify_token",
        return_value={"sub": "abc", "email": admin.email},
    ):
        with patch("app.auth.deps.get_or_create_user", return_value=admin):
            with patch("app.users.service.get_user_by_id", return_value=admin):
                response = await client.delete(
                    f"/api/admin/users/{admin.id}",
                    headers={"Authorization": "Bearer fake"},
                )

    assert response.status_code == 400
