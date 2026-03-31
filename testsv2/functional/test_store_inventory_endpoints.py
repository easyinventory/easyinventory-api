"""
Functional tests for POST/GET/PATCH/DELETE /api/stores/{store_id}/inventory.

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
    create_product,
    create_store,
    create_store_inventory,
)
from testsv2.functional.conftest import AUTH_HEADER

# ── Helpers ───────────────────────────────────────────────────────────────────


def _org_headers(org_id) -> dict:
    """Return auth + X-Org-Id headers for the given org."""
    return {**AUTH_HEADER, "X-Org-Id": str(org_id)}


def _inventory_url(store_id) -> str:
    return f"/api/stores/{store_id}/inventory"


# ── POST /api/stores/{store_id}/inventory ─────────────────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_stock_product_success(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """POST creates an inventory entry and returns 201 with a full payload."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)

    response = await client.post(
        _inventory_url(store.id),
        json={"product_id": str(product.id), "quantity": 12.5, "unit_price": "3.99"},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["store_id"] == str(store.id)
    assert body["product_id"] == str(product.id)
    assert body["quantity"] == 12.5
    assert body["unit_price"] == "3.9900"
    assert "id" in body
    assert "created_at" in body


@pytest.mark.usefixtures("bypass_auth")
async def test_stock_product_duplicate_returns_409(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Stocking the same product twice in the same store returns 409."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)
    await create_store_inventory(db, store_id=store.id, product_id=product.id)

    response = await client.post(
        _inventory_url(store.id),
        json={"product_id": str(product.id)},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 409


@pytest.mark.usefixtures("bypass_auth")
async def test_stock_product_invalid_store_returns_404(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """POST to an unknown store returns 404."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    product = await create_product(db, org_id=org.id)
    import uuid

    response = await client.post(
        _inventory_url(uuid.uuid4()),
        json={"product_id": str(product.id)},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 404


# ── GET /api/stores/{store_id}/inventory ──────────────────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_list_inventory_empty(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """GET returns an empty list when the store has no inventory."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)

    response = await client.get(
        _inventory_url(store.id), headers=_org_headers(org.id)
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.usefixtures("bypass_auth")
async def test_list_inventory_returns_entries(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """GET returns all inventory entries for the store."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    product_a = await create_product(db, org_id=org.id, name="Alpha")
    product_b = await create_product(db, org_id=org.id, name="Beta")
    await create_store_inventory(
        db, store_id=store.id, product_id=product_a.id, quantity=5.0
    )
    await create_store_inventory(
        db, store_id=store.id, product_id=product_b.id, quantity=8.0
    )

    response = await client.get(
        _inventory_url(store.id), headers=_org_headers(org.id)
    )

    assert response.status_code == 200
    product_ids = {e["product_id"] for e in response.json()}
    assert str(product_a.id) in product_ids
    assert str(product_b.id) in product_ids


# ── GET /api/stores/{store_id}/inventory/{entry_id} ───────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_get_inventory_entry_success(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """GET single entry returns 200 with the correct payload."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)
    entry = await create_store_inventory(
        db, store_id=store.id, product_id=product.id, quantity=7.0
    )

    response = await client.get(
        f"{_inventory_url(store.id)}/{entry.id}", headers=_org_headers(org.id)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(entry.id)
    assert body["quantity"] == 7.0


@pytest.mark.usefixtures("bypass_auth")
async def test_get_inventory_entry_not_found(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """GET single entry returns 404 for an unknown entry ID."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    import uuid

    response = await client.get(
        f"{_inventory_url(store.id)}/{uuid.uuid4()}", headers=_org_headers(org.id)
    )

    assert response.status_code == 404


# ── PATCH /api/stores/{store_id}/inventory/{entry_id} ─────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_update_inventory_entry_success(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """PATCH updates the specified fields and returns 200."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)
    entry = await create_store_inventory(
        db, store_id=store.id, product_id=product.id, quantity=3.0
    )

    response = await client.patch(
        f"{_inventory_url(store.id)}/{entry.id}",
        json={"quantity": 99.0, "low_stock_threshold": 10.0},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["quantity"] == 99.0
    assert body["low_stock_threshold"] == 10.0


# ── DELETE /api/stores/{store_id}/inventory/{entry_id} ────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_delete_inventory_entry_as_owner(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """DELETE returns 204 when called by the org owner."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)
    entry = await create_store_inventory(db, store_id=store.id, product_id=product.id)

    response = await client.delete(
        f"{_inventory_url(store.id)}/{entry.id}", headers=_org_headers(org.id)
    )

    assert response.status_code == 204


@pytest.mark.usefixtures("bypass_auth")
async def test_delete_inventory_entry_as_employee_returns_403(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """DELETE returns 403 when called by a non-owner member."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.EMPLOYEE
    )
    store = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)
    entry = await create_store_inventory(db, store_id=store.id, product_id=product.id)

    response = await client.delete(
        f"{_inventory_url(store.id)}/{entry.id}", headers=_org_headers(org.id)
    )

    assert response.status_code == 403
