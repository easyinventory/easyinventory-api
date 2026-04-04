"""
Unit tests verifying that zone_id is captured on inventory movements.

When an inventory item has an active placement (ended_at IS NULL), the
zone_id from that placement is stored on each new InventoryMovement
created by ``record_receipt`` and ``record_sale``.
"""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.store_inventory.schemas import RecordReceiptRequest, RecordSaleRequest
from app.store_inventory.service import record_receipt, record_sale
from testsv2.factories import (
    create_inventory_placement,
    create_layout_version,
    create_org,
    create_product,
    create_store,
    create_store_inventory,
    create_user,
    create_zone,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _setup_with_placement(db: AsyncSession):
    """Create org → store → layout → zone → inventory → active placement."""
    org = await create_org(db)
    user = await create_user(db)
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(
        db, store_id=store.id, version_number=1, is_active=True
    )
    zone = await create_zone(
        db,
        layout_version_id=layout.id,
        name="Produce",
        color="#22C55E",
        cells=[{"row": 0, "col": 0}],
    )
    product = await create_product(db, org_id=org.id)
    inventory = await create_store_inventory(
        db, store_id=store.id, product_id=product.id, quantity=100.0
    )
    await create_inventory_placement(
        db,
        store_inventory_id=inventory.id,
        zone_id=zone.id,
        placed_by_user_id=user.id,
    )
    return store, inventory, zone, user


async def _setup_without_placement(db: AsyncSession):
    """Create org → store → inventory (no placement)."""
    org = await create_org(db)
    user = await create_user(db)
    store = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)
    inventory = await create_store_inventory(
        db, store_id=store.id, product_id=product.id, quantity=50.0
    )
    return store, inventory, user


# ── record_receipt + zone_id ──────────────────────────────────────────────────


async def test_receipt_captures_zone_id_from_active_placement(
    db: AsyncSession,
) -> None:
    """record_receipt stores the zone_id of the item's active placement."""
    store, inventory, zone, user = await _setup_with_placement(db)

    data = RecordReceiptRequest(quantity=10, unit_cost=Decimal("2.00"))
    movement = await record_receipt(db, inventory.id, store.id, data, user.id)

    assert movement.zone_id == zone.id


async def test_receipt_zone_id_is_none_without_placement(
    db: AsyncSession,
) -> None:
    """record_receipt sets zone_id to None when no active placement exists."""
    store, inventory, user = await _setup_without_placement(db)

    data = RecordReceiptRequest(quantity=5)
    movement = await record_receipt(db, inventory.id, store.id, data, user.id)

    assert movement.zone_id is None


# ── record_sale + zone_id ─────────────────────────────────────────────────────


async def test_sale_captures_zone_id_from_active_placement(
    db: AsyncSession,
) -> None:
    """record_sale stores the zone_id of the item's active placement."""
    store, inventory, zone, user = await _setup_with_placement(db)

    data = RecordSaleRequest(quantity=5, unit_price=Decimal("3.49"))
    movement = await record_sale(db, inventory.id, store.id, data, user.id)

    assert movement.zone_id == zone.id


async def test_sale_zone_id_is_none_without_placement(
    db: AsyncSession,
) -> None:
    """record_sale sets zone_id to None when no active placement exists."""
    store, inventory, user = await _setup_without_placement(db)

    data = RecordSaleRequest(quantity=3)
    movement = await record_sale(db, inventory.id, store.id, data, user.id)

    assert movement.zone_id is None


# ── zone_name property ────────────────────────────────────────────────────────


async def test_movement_zone_name_property(db: AsyncSession) -> None:
    """The zone_name property returns the related zone's name."""
    store, inventory, zone, user = await _setup_with_placement(db)

    data = RecordReceiptRequest(quantity=10)
    movement = await record_receipt(db, inventory.id, store.id, data, user.id)

    assert movement.zone_name == "Produce"


async def test_movement_zone_name_none_without_zone(db: AsyncSession) -> None:
    """The zone_name property returns None when there is no zone."""
    store, inventory, user = await _setup_without_placement(db)

    data = RecordReceiptRequest(quantity=5)
    movement = await record_receipt(db, inventory.id, store.id, data, user.id)

    assert movement.zone_name is None


# ── Ended placement is ignored ────────────────────────────────────────────────


async def test_ended_placement_is_not_used(db: AsyncSession) -> None:
    """A placement with ended_at set is not an active placement."""
    from datetime import datetime, timezone

    org = await create_org(db)
    user = await create_user(db)
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(
        db, store_id=store.id, version_number=1, is_active=True
    )
    zone = await create_zone(db, layout_version_id=layout.id, name="Old Zone")
    product = await create_product(db, org_id=org.id)
    inventory = await create_store_inventory(
        db, store_id=store.id, product_id=product.id, quantity=50.0
    )
    # Create a placement that has already ended.
    await create_inventory_placement(
        db,
        store_inventory_id=inventory.id,
        zone_id=zone.id,
        placed_by_user_id=user.id,
        ended_at=datetime.now(timezone.utc),
    )

    data = RecordReceiptRequest(quantity=10)
    movement = await record_receipt(db, inventory.id, store.id, data, user.id)

    assert movement.zone_id is None
