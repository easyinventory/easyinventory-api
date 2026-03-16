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
        "app.api.deps.verify_token", return_value={"sub": "abc", "email": user.email}
    ):
        with patch("app.api.deps.get_or_create_user", return_value=user):
            response = await client.post(
                "/api/admin/orgs",
                json={"name": "New Org", "owner_email": "owner@test.com"},
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 403


async def test_admin_can_create_org_with_new_email(app, client):
    """SYSTEM_ADMIN can create an org with an unknown email → Cognito invite."""
    admin = _mock_admin()

    mock_placeholder = MagicMock()
    mock_placeholder.id = uuid.uuid4()

    mock_membership = MagicMock()
    mock_membership.id = uuid.uuid4()

    mock_db = _mock_db_session()

    with _db_override(app, mock_db):
        with patch(
            "app.api.deps.verify_token",
            return_value={"sub": "abc", "email": admin.email},
        ):
            with patch("app.api.deps.get_or_create_user", return_value=admin):
                with patch(
                    "app.services.org_service.find_user_by_email", return_value=None
                ):
                    with patch(
                        "app.api.routes.admin.invite_cognito_user"
                    ) as mock_cognito:
                        with patch(
                            "app.services.org_service.create_placeholder_user",
                            return_value=mock_placeholder,
                        ):
                            with patch(
                                "app.services.org_service.create_membership",
                                return_value=mock_membership,
                            ):
                                response = await client.post(
                                    "/api/admin/orgs",
                                    json={
                                        "name": "Client Corp",
                                        "owner_email": "newclient@test.com",
                                    },
                                    headers={"Authorization": "Bearer fake"},
                                )

                        mock_cognito.assert_called_once_with("newclient@test.com")
    assert response.status_code == 201


async def test_admin_can_create_org_with_existing_user(app, client):
    """Existing user should become active owner without Cognito invite."""
    admin = _mock_admin()
    existing_user = MagicMock(spec=User)
    existing_user.id = uuid.uuid4()
    existing_user.email = "existing@test.com"

    mock_db = _mock_db_session()

    with _db_override(app, mock_db):
        with patch(
            "app.api.deps.verify_token",
            return_value={"sub": "abc", "email": admin.email},
        ):
            with patch("app.api.deps.get_or_create_user", return_value=admin):
                with patch(
                    "app.services.org_service.find_user_by_email",
                    return_value=existing_user,
                ):
                    with patch(
                        "app.services.org_service.find_existing_membership",
                        return_value=None,
                    ):
                        with patch(
                            "app.api.routes.admin.invite_cognito_user"
                        ) as mock_cognito:
                            with patch("app.services.org_service.create_membership"):
                                response = await client.post(
                                    "/api/admin/orgs",
                                    json={
                                        "name": "Existing Client",
                                        "owner_email": "existing@test.com",
                                    },
                                    headers={"Authorization": "Bearer fake"},
                                )

                            # Should NOT call Cognito for existing user
                            mock_cognito.assert_not_called()
    assert response.status_code == 201


async def test_create_org_returns_401_without_token(client):
    response = await client.post(
        "/api/admin/orgs",
        json={"name": "Test", "owner_email": "test@test.com"},
    )
    assert response.status_code == 401


async def test_list_orgs_returns_403_for_non_admin(client):
    user = _mock_regular_user()
    with patch(
        "app.api.deps.verify_token", return_value={"sub": "abc", "email": user.email}
    ):
        with patch("app.api.deps.get_or_create_user", return_value=user):
            response = await client.get(
                "/api/admin/orgs",
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 403
