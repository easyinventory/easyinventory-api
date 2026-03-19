import uuid
from contextlib import contextmanager
from unittest.mock import patch, MagicMock, AsyncMock

from app.orgs.deps import get_current_org_membership
from app.core.database import get_db
from app.models.user import User
from app.models.org_membership import OrgMembership


def _mock_user(email="owner@test.com"):
    mock = MagicMock(spec=User)
    mock.id = uuid.uuid4()
    mock.email = email
    mock.system_role = "SYSTEM_USER"
    mock.is_active = True
    return mock


def _mock_membership(role="ORG_OWNER", org_id=None, member_id=None, is_active=True):
    mock = MagicMock(spec=OrgMembership)
    mock.id = member_id or uuid.uuid4()
    mock.org_id = org_id or uuid.uuid4()
    mock.org_role = role
    mock.is_active = is_active
    mock.user_id = uuid.uuid4()
    mock.joined_at = "2026-03-13T00:00:00+00:00"
    return mock


@contextmanager
def _org_dependency_overrides(app, membership):
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_org_membership] = lambda: membership
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_org_membership, None)


# ── Invite permission tests ──


async def test_employee_cannot_invite(app, client):
    membership = _mock_membership(role="ORG_EMPLOYEE")
    with _org_dependency_overrides(app, membership):
        response = await client.post(
            "/api/orgs/invite",
            json={"email": "new@test.com", "org_role": "ORG_EMPLOYEE"},
            headers={"Authorization": "Bearer fake"},
        )
    assert response.status_code == 403


async def test_admin_cannot_invite_as_admin(app, client):
    membership = _mock_membership(role="ORG_ADMIN")
    with _org_dependency_overrides(app, membership):
        response = await client.post(
            "/api/orgs/invite",
            json={"email": "new@test.com", "org_role": "ORG_ADMIN"},
            headers={"Authorization": "Bearer fake"},
        )
    assert response.status_code == 403


async def test_cannot_invite_as_owner(app, client):
    membership = _mock_membership(role="ORG_OWNER")
    with _org_dependency_overrides(app, membership):
        response = await client.post(
            "/api/orgs/invite",
            json={"email": "new@test.com", "org_role": "ORG_OWNER"},
            headers={"Authorization": "Bearer fake"},
        )
    assert response.status_code == 400


async def test_duplicate_active_member_returns_400(app, client):
    membership = _mock_membership(role="ORG_OWNER")
    existing_user = _mock_user(email="exists@test.com")
    existing_membership = _mock_membership(is_active=True)

    with _org_dependency_overrides(app, membership):
        with patch(
            "app.users.service.find_user_by_email", return_value=existing_user
        ):
            with patch(
                "app.orgs.service.find_existing_membership",
                return_value=existing_membership,
            ):
                response = await client.post(
                    "/api/orgs/invite",
                    json={"email": "exists@test.com", "org_role": "ORG_EMPLOYEE"},
                    headers={"Authorization": "Bearer fake"},
                )
    assert response.status_code == 400
    assert "already a member" in response.json()["detail"]


async def test_duplicate_pending_invite_returns_400(app, client):
    membership = _mock_membership(role="ORG_OWNER")
    placeholder_user = _mock_user(email="pending@test.com")
    pending_membership = _mock_membership(is_active=False)

    with _org_dependency_overrides(app, membership):
        with patch(
            "app.users.service.find_user_by_email", return_value=placeholder_user
        ):
            with patch(
                "app.orgs.service.find_existing_membership",
                return_value=pending_membership,
            ):
                response = await client.post(
                    "/api/orgs/invite",
                    json={"email": "pending@test.com", "org_role": "ORG_EMPLOYEE"},
                    headers={"Authorization": "Bearer fake"},
                )
    assert response.status_code == 400
    assert "already been invited" in response.json()["detail"]


async def test_invite_unknown_email_calls_cognito(app, client):
    """Inviting an unknown email should create a Cognito account."""
    membership = _mock_membership(role="ORG_OWNER")

    with _org_dependency_overrides(app, membership):
        with patch("app.users.service.find_user_by_email", return_value=None):
            with patch(
                "app.services.invite_service.invite_cognito_user"
            ) as mock_cognito:
                with patch(
                    "app.users.service.create_placeholder_user"
                ) as mock_placeholder:
                    placeholder_user = MagicMock(id=uuid.uuid4())
                    mock_placeholder.return_value = placeholder_user

                    with patch(
                        "app.orgs.service.create_membership"
                    ) as mock_membership_create:
                        mock_membership_create.return_value = MagicMock(
                            id=uuid.uuid4(),
                            user_id=placeholder_user.id,
                            org_role="ORG_EMPLOYEE",
                            is_active=False,
                            joined_at="2026-03-13T00:00:00+00:00",
                        )

                        response = await client.post(
                            "/api/orgs/invite",
                            json={"email": "new@test.com", "org_role": "ORG_EMPLOYEE"},
                            headers={"Authorization": "Bearer fake"},
                        )

    assert response.status_code == 201
    mock_cognito.assert_called_once_with("new@test.com")


async def test_invite_existing_email_does_not_call_cognito(app, client):
    """Inviting an existing user should NOT create a Cognito account."""
    membership = _mock_membership(role="ORG_OWNER")
    existing_user = _mock_user(email="exists@test.com")

    with _org_dependency_overrides(app, membership):
        with patch(
            "app.users.service.find_user_by_email", return_value=existing_user
        ):
            with patch(
                "app.orgs.service.find_existing_membership", return_value=None
            ):
                with patch(
                    "app.services.invite_service.invite_cognito_user"
                ) as mock_cognito:
                    with patch(
                        "app.orgs.service.create_membership"
                    ) as mock_create:
                        mock_create.return_value = MagicMock(
                            id=uuid.uuid4(),
                            user_id=existing_user.id,
                            org_role="ORG_EMPLOYEE",
                            is_active=True,
                            joined_at="2026-03-13T00:00:00+00:00",
                        )

                        response = await client.post(
                            "/api/orgs/invite",
                            json={
                                "email": "exists@test.com",
                                "org_role": "ORG_EMPLOYEE",
                            },
                            headers={"Authorization": "Bearer fake"},
                        )

    assert response.status_code == 201
    mock_cognito.assert_not_called()


# ── Owner protection tests ──


async def test_cannot_deactivate_owner(app, client):
    actor = _mock_membership(role="ORG_OWNER")
    target = _mock_membership(role="ORG_OWNER", member_id=uuid.uuid4())

    with _org_dependency_overrides(app, actor):
        with patch(
            "app.orgs.service.get_membership_by_id", return_value=target
        ):
            response = await client.patch(
                f"/api/orgs/members/{target.id}/deactivate",
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 403
    assert "owner" in response.json()["detail"].lower()


async def test_cannot_remove_owner(app, client):
    actor = _mock_membership(role="ORG_OWNER")
    target = _mock_membership(role="ORG_OWNER", member_id=uuid.uuid4())

    with _org_dependency_overrides(app, actor):
        with patch(
            "app.orgs.service.get_membership_by_id", return_value=target
        ):
            response = await client.delete(
                f"/api/orgs/members/{target.id}",
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 403


async def test_cannot_change_owner_role(app, client):
    actor = _mock_membership(role="ORG_OWNER")
    target = _mock_membership(role="ORG_OWNER", member_id=uuid.uuid4())

    with _org_dependency_overrides(app, actor):
        with patch(
            "app.orgs.service.get_membership_by_id", return_value=target
        ):
            response = await client.patch(
                f"/api/orgs/members/{target.id}/role",
                json={"org_role": "ORG_EMPLOYEE"},
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 403


# ── Admin hierarchy tests ──


async def test_admin_cannot_deactivate_admin(app, client):
    actor = _mock_membership(role="ORG_ADMIN")
    target = _mock_membership(role="ORG_ADMIN", member_id=uuid.uuid4())

    with _org_dependency_overrides(app, actor):
        with patch(
            "app.orgs.service.get_membership_by_id", return_value=target
        ):
            response = await client.patch(
                f"/api/orgs/members/{target.id}/deactivate",
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 403


async def test_admin_cannot_remove_admin(app, client):
    actor = _mock_membership(role="ORG_ADMIN")
    target = _mock_membership(role="ORG_ADMIN", member_id=uuid.uuid4())

    with _org_dependency_overrides(app, actor):
        with patch(
            "app.orgs.service.get_membership_by_id", return_value=target
        ):
            response = await client.delete(
                f"/api/orgs/members/{target.id}",
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 403


# ── Auth tests ──


async def test_members_returns_401_without_token(client):
    response = await client.get("/api/orgs/members")
    assert response.status_code == 401
