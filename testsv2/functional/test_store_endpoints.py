"""
Functional tests for the store routes (GET /api/stores, POST /api/stores).

Uses the real DB with transaction rollback, a real httpx AsyncClient,
and bypasses Cognito auth via the ``bypass_auth`` fixture.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import OrgRole
from app.models.user import User
from testsv2.factories import (
    create_membership,
    create_org,
    create_store,
)
from testsv2.functional.conftest import AUTH_HEADER


# ── Helpers ───────────────────────────────────────────────────────────────────


def _org_headers(org_id) -> dict:
    """Return auth + X-Org-Id headers for the given org."""
    return {**AUTH_HEADER, "X-Org-Id": str(org_id)}


# ── GET /api/stores ────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_list_stores_empty(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Returns an empty list when the org has no stores."""
    org = await create_org(db, name="Empty Org")
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)

    response = await client.get("/api/stores", headers=_org_headers(org.id))

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.usefixtures("bypass_auth")
async def test_list_stores_returns_stores(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Returns all stores that belong to the current org."""
    org = await create_org(db, name="Multi-Store Org")
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)
    await create_store(db, org_id=org.id, name="Store A")
    await create_store(db, org_id=org.id, name="Store B")

    response = await client.get("/api/stores", headers=_org_headers(org.id))

    assert response.status_code == 200
    names = {s["name"] for s in response.json()}
    assert names == {"Store A", "Store B"}


@pytest.mark.usefixtures("bypass_auth")
async def test_list_stores_scoped_to_org(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Stores from other orgs are not included in the response."""
    org_a = await create_org(db, name="Org A")
    org_b = await create_org(db, name="Org B")
    await create_membership(db, org_id=org_a.id, user_id=test_user.id, org_role=OrgRole.OWNER)
    await create_store(db, org_id=org_a.id, name="Org A Store")
    await create_store(db, org_id=org_b.id, name="Org B Store")

    response = await client.get("/api/stores", headers=_org_headers(org_a.id))

    assert response.status_code == 200
    names = [s["name"] for s in response.json()]
    assert names == ["Org A Store"]
    assert "Org B Store" not in names


# ── POST /api/stores ───────────────────────────────────────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_create_store_as_owner(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Owner can create a new store; response is 201 with full StoreRead payload."""
    org = await create_org(db, name="Owner Org")
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)

    response = await client.post(
        "/api/stores",
        json={"name": "Brand New Store"},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Brand New Store"
    assert body["org_id"] == str(org.id)
    assert body["is_active"] is True
    assert "id" in body
    assert "created_at" in body
    assert "updated_at" in body


@pytest.mark.usefixtures("bypass_auth")
async def test_create_store_requires_owner_role(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Non-owner membership receives 403 on store creation."""
    org = await create_org(db, name="Employee Org")
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.EMPLOYEE
    )

    response = await client.post(
        "/api/stores",
        json={"name": "Should Fail"},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 403


@pytest.mark.usefixtures("bypass_auth")
async def test_create_store_missing_name_returns_422(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Missing or empty name triggers a 422 validation error."""
    org = await create_org(db, name="Validation Org")
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)

    response = await client.post(
        "/api/stores",
        json={"name": ""},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 422
