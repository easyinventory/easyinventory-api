"""
Functional tests for zone_id on inventory movement endpoints.

  POST  /api/stores/{store_id}/inventory/{id}/receipts
  POST  /api/stores/{store_id}/inventory/{id}/sales
  GET   /api/stores/{store_id}/inventory/{id}/movements

Verifies that zone_id and zone_name appear in movement responses when
the inventory item has an active placement.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import OrgRole
from app.models.user import User
from testsv2.factories import (
    create_inventory_placement,
    create_layout_version,
    create_membership,
    create_org,
    create_product,
    create_store,
    create_store_inventory,
    create_zone,
)
from testsv2.functional.conftest import AUTH_HEADER

# ── Helpers ───────────────────────────────────────────────────────────────────


def _org_headers(org_id) -> dict:
    return {**AUTH_HEADER, "X-Org-Id": str(org_id)}


# ── POST .../receipts — zone_id present ───────────────────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_receipt_response_includes_zone_id(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Receipt response contains zone_id and zone_name from the active placement."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(
        db, store_id=store.id, version_number=1, is_active=True
    )
    zone = await create_zone(
        db, layout_version_id=layout.id, name="Produce", color="#22C55E"
    )
    product = await create_product(db, org_id=org.id)
    inventory = await create_store_inventory(
        db, store_id=store.id, product_id=product.id, quantity=0
    )
    await create_inventory_placement(
        db,
        store_inventory_id=inventory.id,
        zone_id=zone.id,
        placed_by_user_id=test_user.id,
    )

    response = await client.post(
        f"/api/stores/{store.id}/inventory/{inventory.id}/receipts",
        json={"quantity": 10, "unit_cost": "2.50"},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["zone_id"] == str(zone.id)
    assert body["zone_name"] == "Produce"


# ── POST .../receipts — no placement ─────────────────────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_receipt_response_zone_id_null_without_placement(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Receipt without an active placement returns zone_id = null."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)
    inventory = await create_store_inventory(
        db, store_id=store.id, product_id=product.id, quantity=0
    )

    response = await client.post(
        f"/api/stores/{store.id}/inventory/{inventory.id}/receipts",
        json={"quantity": 5},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["zone_id"] is None
    assert body["zone_name"] is None


# ── POST .../sales — zone_id present ─────────────────────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_sale_response_includes_zone_id(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Sale response contains zone_id from the active placement."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(
        db, store_id=store.id, version_number=1, is_active=True
    )
    zone = await create_zone(
        db, layout_version_id=layout.id, name="Dairy", color="#3B82F6"
    )
    product = await create_product(db, org_id=org.id)
    inventory = await create_store_inventory(
        db, store_id=store.id, product_id=product.id, quantity=50.0
    )
    await create_inventory_placement(
        db,
        store_inventory_id=inventory.id,
        zone_id=zone.id,
        placed_by_user_id=test_user.id,
    )

    response = await client.post(
        f"/api/stores/{store.id}/inventory/{inventory.id}/sales",
        json={"quantity": 5, "unit_price": "4.99"},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["zone_id"] == str(zone.id)
    assert body["zone_name"] == "Dairy"


# ── GET .../movements — zone_id in list ───────────────────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_movement_list_includes_zone_fields(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """GET movements returns zone_id and zone_name on each entry."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(
        db, store_id=store.id, version_number=1, is_active=True
    )
    zone = await create_zone(
        db, layout_version_id=layout.id, name="Dry Goods", color="#F59E0B"
    )
    product = await create_product(db, org_id=org.id)
    inventory = await create_store_inventory(
        db, store_id=store.id, product_id=product.id, quantity=0
    )
    await create_inventory_placement(
        db,
        store_inventory_id=inventory.id,
        zone_id=zone.id,
        placed_by_user_id=test_user.id,
    )

    # Create a receipt so there's a movement to list
    await client.post(
        f"/api/stores/{store.id}/inventory/{inventory.id}/receipts",
        json={"quantity": 20},
        headers=_org_headers(org.id),
    )

    response = await client.get(
        f"/api/stores/{store.id}/inventory/{inventory.id}/movements",
        headers=_org_headers(org.id),
    )

    assert response.status_code == 200
    movements = response.json()
    assert len(movements) == 1
    assert movements[0]["zone_id"] == str(zone.id)
    assert movements[0]["zone_name"] == "Dry Goods"
