"""
Unit tests for inventory movement service functions (record_receipt, record_sale).
Uses the real DB with per-test transaction rollback — no HTTP layer.
"""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFound
from app.store_inventory.schemas import RecordReceiptRequest, RecordSaleRequest
from app.store_inventory.service import record_receipt, record_sale
from testsv2.factories import (
    create_org,
    create_product,
    create_store,
    create_store_inventory,
    create_user,
)

# ── record_receipt ────────────────────────────────────────────────────────────


async def test_record_receipt_creates_movement(db: AsyncSession) -> None:
    """record_receipt returns an InventoryMovement with correct fields."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)
    inventory = await create_store_inventory(
        db, store_id=store.id, product_id=product.id
    )
    user = await create_user(db)

    data = RecordReceiptRequest(quantity=10, unit_cost=Decimal("5.00"))
    movement = await record_receipt(db, inventory.id, store.id, data, user.id)

    assert movement.id is not None
    assert movement.store_inventory_id == inventory.id
    assert movement.movement_type.value == "receipt"
    assert movement.quantity == 10
    assert movement.unit_cost == Decimal("5.00")
    assert movement.performed_by_user_id == user.id
    assert movement.created_at is not None


async def test_record_receipt_increases_quantity(db: AsyncSession) -> None:
    """record_receipt increments the inventory quantity by the received amount."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)
    inventory = await create_store_inventory(
        db, store_id=store.id, product_id=product.id, quantity=5.0
    )
    user = await create_user(db)

    data = RecordReceiptRequest(quantity=10)
    await record_receipt(db, inventory.id, store.id, data, user.id)

    await db.refresh(inventory)
    assert inventory.quantity == 15.0


async def test_record_receipt_not_found(db: AsyncSession) -> None:
    """record_receipt raises NotFound when the inventory entry does not exist."""
    from uuid import uuid4

    user = await create_user(db)
    data = RecordReceiptRequest(quantity=5)

    with pytest.raises(NotFound):
        await record_receipt(db, uuid4(), uuid4(), data, user.id)


# ── record_sale ───────────────────────────────────────────────────────────────


async def test_record_sale_creates_movement(db: AsyncSession) -> None:
    """record_sale returns an InventoryMovement with correct fields."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)
    inventory = await create_store_inventory(
        db, store_id=store.id, product_id=product.id, quantity=20.0
    )
    user = await create_user(db)

    data = RecordSaleRequest(quantity=5, unit_price=Decimal("9.99"))
    movement = await record_sale(db, inventory.id, store.id, data, user.id)

    assert movement.id is not None
    assert movement.store_inventory_id == inventory.id
    assert movement.movement_type.value == "sale"
    assert movement.quantity == 5
    assert movement.unit_price == Decimal("9.99")
    assert movement.performed_by_user_id == user.id


async def test_record_sale_decreases_quantity(db: AsyncSession) -> None:
    """record_sale decrements the inventory quantity by the sold amount."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)
    inventory = await create_store_inventory(
        db, store_id=store.id, product_id=product.id, quantity=20.0
    )
    user = await create_user(db)

    data = RecordSaleRequest(quantity=5)
    await record_sale(db, inventory.id, store.id, data, user.id)

    await db.refresh(inventory)
    assert inventory.quantity == 15.0


async def test_record_sale_insufficient_stock(db: AsyncSession) -> None:
    """record_sale raises AppError when requested quantity exceeds available stock."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)
    inventory = await create_store_inventory(
        db, store_id=store.id, product_id=product.id, quantity=5.0
    )
    user = await create_user(db)

    data = RecordSaleRequest(quantity=10)

    with pytest.raises(AppError) as exc_info:
        await record_sale(db, inventory.id, store.id, data, user.id)

    assert exc_info.value.status_code == 400


async def test_record_sale_exact_quantity_succeeds(db: AsyncSession) -> None:
    """record_sale succeeds when selling exactly the available quantity."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)
    inventory = await create_store_inventory(
        db, store_id=store.id, product_id=product.id, quantity=10.0
    )
    user = await create_user(db)

    data = RecordSaleRequest(quantity=10)
    movement = await record_sale(db, inventory.id, store.id, data, user.id)

    await db.refresh(inventory)
    assert movement.quantity == 10
    assert inventory.quantity == 0.0


async def test_record_sale_not_found(db: AsyncSession) -> None:
    """record_sale raises NotFound when the inventory entry does not exist."""
    from uuid import uuid4

    user = await create_user(db)
    data = RecordSaleRequest(quantity=1)

    with pytest.raises(NotFound):
        await record_sale(db, uuid4(), uuid4(), data, user.id)


# ── Cross-store isolation ────────────────────────────────────────────────────


async def test_record_receipt_wrong_store_raises_not_found(db: AsyncSession) -> None:
    """record_receipt raises NotFound when the inventory_id belongs to a different store."""
    org = await create_org(db)
    store_a = await create_store(db, org_id=org.id)
    store_b = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)
    # inventory belongs to store_a
    inventory = await create_store_inventory(
        db, store_id=store_a.id, product_id=product.id
    )
    user = await create_user(db)

    data = RecordReceiptRequest(quantity=5)
    with pytest.raises(NotFound):
        # passing store_b.id — should be rejected
        await record_receipt(db, inventory.id, store_b.id, data, user.id)


async def test_record_sale_wrong_store_raises_not_found(db: AsyncSession) -> None:
    """record_sale raises NotFound when the inventory_id belongs to a different store."""
    org = await create_org(db)
    store_a = await create_store(db, org_id=org.id)
    store_b = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)
    # inventory belongs to store_a with enough stock
    inventory = await create_store_inventory(
        db, store_id=store_a.id, product_id=product.id, quantity=20.0
    )
    user = await create_user(db)

    data = RecordSaleRequest(quantity=5)
    with pytest.raises(NotFound):
        # passing store_b.id — should be rejected
        await record_sale(db, inventory.id, store_b.id, data, user.id)
