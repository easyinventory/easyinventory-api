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
    """GET returns a paginated envelope with an empty items list when the store has no inventory."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)

    response = await client.get(_inventory_url(store.id), headers=_org_headers(org.id))

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1
    assert body["page_size"] == 20


@pytest.mark.usefixtures("bypass_auth")
async def test_list_inventory_returns_entries(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """GET returns paginated inventory entries with joined product information."""
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

    response = await client.get(_inventory_url(store.id), headers=_org_headers(org.id))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    product_ids = {e["product_id"] for e in body["items"]}
    assert str(product_a.id) in product_ids
    assert str(product_b.id) in product_ids
    # Verify joined product data is present
    item = next(e for e in body["items"] if e["product_id"] == str(product_a.id))
    assert item["product"]["name"] == "Alpha"


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


@pytest.mark.usefixtures("bypass_auth")
async def test_stock_product_as_employee_succeeds(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """POST is open to any org member, not just owners."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.EMPLOYEE
    )
    store = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)

    response = await client.post(
        _inventory_url(store.id),
        json={"product_id": str(product.id)},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 201


@pytest.mark.usefixtures("bypass_auth")
async def test_stock_product_cross_org_product_returns_404(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """POST rejects a product_id that belongs to a different org (tenant isolation)."""
    org = await create_org(db, name="Org A")
    other_org = await create_org(db, name="Org B")
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    foreign_product = await create_product(db, org_id=other_org.id)

    response = await client.post(
        _inventory_url(store.id),
        json={"product_id": str(foreign_product.id)},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 404


# ── GET /api/stores/{store_id}/inventory: search & filter ─────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_list_inventory_search_by_name(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """?search= filters results to entries whose product name matches."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    widget = await create_product(db, org_id=org.id, name="Blue Widget")
    gadget = await create_product(db, org_id=org.id, name="Red Gadget")
    await create_store_inventory(db, store_id=store.id, product_id=widget.id)
    await create_store_inventory(db, store_id=store.id, product_id=gadget.id)

    response = await client.get(
        _inventory_url(store.id),
        params={"search": "widget"},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["product_id"] == str(widget.id)


@pytest.mark.usefixtures("bypass_auth")
async def test_list_inventory_search_by_category(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """?search= also matches against product category."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    tool = await create_product(db, org_id=org.id, name="Wrench", category="Tools")
    snack = await create_product(db, org_id=org.id, name="Chips", category="Food")
    await create_store_inventory(db, store_id=store.id, product_id=tool.id)
    await create_store_inventory(db, store_id=store.id, product_id=snack.id)

    response = await client.get(
        _inventory_url(store.id),
        params={"search": "TOOLS"},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["product_id"] == str(tool.id)


@pytest.mark.usefixtures("bypass_auth")
async def test_list_inventory_category_filter(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """?category= filters results to entries whose product category matches."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    hardware = await create_product(db, org_id=org.id, name="Bolt", category="Hardware")
    food = await create_product(db, org_id=org.id, name="Bread", category="Food")
    await create_store_inventory(db, store_id=store.id, product_id=hardware.id)
    await create_store_inventory(db, store_id=store.id, product_id=food.id)

    response = await client.get(
        _inventory_url(store.id),
        params={"category": "hardware"},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["product_id"] == str(hardware.id)


# ── GET /api/stores/{store_id}/inventory: pagination ─────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_list_inventory_pagination_page_size(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """?page_size= limits the number of items returned, total reflects all rows."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    for i in range(5):
        p = await create_product(db, org_id=org.id, name=f"Prod {i}")
        await create_store_inventory(db, store_id=store.id, product_id=p.id)

    response = await client.get(
        _inventory_url(store.id),
        params={"page": 1, "page_size": 2},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2


@pytest.mark.usefixtures("bypass_auth")
async def test_list_inventory_pagination_no_overlap(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Page 1 and page 2 return non-overlapping items."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    for i in range(4):
        p = await create_product(db, org_id=org.id, name=f"Item {i:02d}")
        await create_store_inventory(db, store_id=store.id, product_id=p.id)

    page1 = (
        await client.get(
            _inventory_url(store.id),
            params={"page": 1, "page_size": 2},
            headers=_org_headers(org.id),
        )
    ).json()["items"]
    page2 = (
        await client.get(
            _inventory_url(store.id),
            params={"page": 2, "page_size": 2},
            headers=_org_headers(org.id),
        )
    ).json()["items"]

    page1_ids = {e["id"] for e in page1}
    page2_ids = {e["id"] for e in page2}
    assert page1_ids.isdisjoint(page2_ids)
    assert len(page2) == 2
