"""
Functional tests for POST /api/admin/orgs.

Uses a real DB session + httpx client. Cognito/invite calls are mocked
at the route boundary since we don't have Cognito in the test environment.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.core.roles import OrgRole, SystemRole
from app.models.org_membership import OrgMembership
from app.models.store import Store
from app.models.user import User
from testsv2.factories import create_user

AUTH_HEADER = {"Authorization": "Bearer fake-test-token"}


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def admin_user(db: AsyncSession) -> User:
    """A SYSTEM_ADMIN user for admin endpoint tests."""
    return await create_user(
        db,
        email="sysadmin@example.com",
        system_role=SystemRole.ADMIN,
    )


@pytest.fixture
def bypass_auth_admin(app, admin_user: User):
    """Override get_current_user to return the admin user."""

    async def _override():
        return admin_user

    app.dependency_overrides[get_current_user] = _override
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("bypass_auth_admin")
async def test_admin_can_create_org(
    client: AsyncClient,
    db: AsyncSession,
) -> None:
    """SYSTEM_ADMIN can create an org; response is 201 with org details."""
    with patch(
        "app.admin.routes_orgs.invite_user_to_org",
        new_callable=AsyncMock,
    ) as mock_invite:
        mock_invite.return_value = AsyncMock(spec=OrgMembership)

        response = await client.post(
            "/api/admin/orgs",
            json={"name": "Client Corp", "owner_email": "owner@clientcorp.com"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Client Corp"
    assert body["owner_email"] == "owner@clientcorp.com"


@pytest.mark.usefixtures("bypass_auth_admin")
async def test_create_org_auto_creates_store(
    client: AsyncClient,
    db: AsyncSession,
) -> None:
    """Creating an org via the admin endpoint also creates a default store."""
    with patch(
        "app.admin.routes_orgs.invite_user_to_org",
        new_callable=AsyncMock,
    ):
        response = await client.post(
            "/api/admin/orgs",
            json={"name": "Store Test Org", "owner_email": "owner@storetest.com"},
            headers=AUTH_HEADER,
        )

    assert response.status_code == 201
    org_id = response.json()["id"]

    # Verify the store was auto-created in the DB
    result = await db.execute(select(Store).where(Store.org_id == org_id))
    stores = result.scalars().all()
    assert len(stores) == 1
    assert stores[0].name == "Store Test Org Default Store"
    assert stores[0].is_active is True


@pytest.mark.usefixtures("bypass_auth_admin")
async def test_create_org_calls_invite(
    client: AsyncClient,
    db: AsyncSession,
) -> None:
    """Creating an org triggers invite_user_to_org with the owner email."""
    with patch(
        "app.admin.routes_orgs.invite_user_to_org",
        new_callable=AsyncMock,
    ) as mock_invite:
        mock_invite.return_value = AsyncMock(spec=OrgMembership)

        await client.post(
            "/api/admin/orgs",
            json={"name": "New Corp", "owner_email": "newowner@corp.com"},
            headers=AUTH_HEADER,
        )

    mock_invite.assert_awaited_once()
    call_kwargs = mock_invite.call_args.kwargs
    assert call_kwargs["email"] == "newowner@corp.com"
    assert call_kwargs["org_role"] == OrgRole.OWNER
    assert call_kwargs["is_new_org"] is True


async def test_non_admin_cannot_create_org(
    app,
    client: AsyncClient,
    db: AsyncSession,
) -> None:
    """SYSTEM_USER gets 403 when attempting to create an org."""
    regular_user = await create_user(db, email="regular@example.com")

    async def _override():
        return regular_user

    app.dependency_overrides[get_current_user] = _override
    try:
        response = await client.post(
            "/api/admin/orgs",
            json={"name": "Test", "owner_email": "owner@test.com"},
            headers=AUTH_HEADER,
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 403
