"""
Unit tests for app.store_inventory.service using the real DB
with per-test transaction rollback (no HTTP layer).
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFound
from app.store_inventory.service import (
    add_product,
    delete_entry,
    get_entry,
    list_inventory,
    update_entry,
)
from testsv2.factories import (
    create_org,
    create_product,
    create_store,
    create_store_inventory,
)

# ── add_product ───────────────────────────────────────────────────────────────


async def test_add_product_creates_entry(db: AsyncSession) -> None:
    """add_product returns a persisted StoreInventory entry with correct fields."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)

    entry = await add_product(
        db,
        store_id=store.id,
        org_id=org.id,
        product_id=product.id,
        quantity=10.0,
        unit_price=Decimal("4.99"),
        low_stock_threshold=2.0,
    )

    assert entry.id is not None
    assert entry.store_id == store.id
    assert entry.product_id == product.id
    assert entry.quantity == 10.0
    assert entry.unit_price == Decimal("4.99")
    assert entry.low_stock_threshold == 2.0
    assert entry.created_at is not None


async def test_add_product_default_quantity_is_zero(db: AsyncSession) -> None:
    """add_product defaults quantity to 0.0 when not provided."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)

    entry = await add_product(
        db, store_id=store.id, org_id=org.id, product_id=product.id
    )

    assert entry.quantity == 0.0


async def test_add_product_duplicate_raises_409(db: AsyncSession) -> None:
    """add_product raises AppError(409) when the product is already in the store."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)

    await create_store_inventory(db, store_id=store.id, product_id=product.id)

    with pytest.raises(AppError) as exc_info:
        await add_product(db, store_id=store.id, org_id=org.id, product_id=product.id)

    assert exc_info.value.status_code == 409


async def test_add_product_unknown_product_raises_not_found(db: AsyncSession) -> None:
    """add_product raises NotFound when the product does not exist in the org."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)
    other_org = await create_org(db, name="Other Org")
    product = await create_product(db, org_id=other_org.id)

    with pytest.raises(NotFound):
        await add_product(db, store_id=store.id, org_id=org.id, product_id=product.id)


# ── list_inventory ────────────────────────────────────────────────────────────


async def test_list_inventory_returns_entries(db: AsyncSession) -> None:
    """list_inventory returns all entries for the store."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)
    product_a = await create_product(db, org_id=org.id, name="Product A")
    product_b = await create_product(db, org_id=org.id, name="Product B")

    await create_store_inventory(db, store_id=store.id, product_id=product_a.id)
    await create_store_inventory(db, store_id=store.id, product_id=product_b.id)

    entries = await list_inventory(db, store_id=store.id)

    assert len(entries) == 2
    product_ids = {e.product_id for e in entries}
    assert product_ids == {product_a.id, product_b.id}


async def test_list_inventory_scoped_to_store(db: AsyncSession) -> None:
    """list_inventory does not return entries from other stores."""
    org = await create_org(db)
    store_a = await create_store(db, org_id=org.id, name="Store A")
    store_b = await create_store(db, org_id=org.id, name="Store B")
    product = await create_product(db, org_id=org.id)

    await create_store_inventory(db, store_id=store_b.id, product_id=product.id)

    entries = await list_inventory(db, store_id=store_a.id)

    assert entries == []


async def test_list_inventory_empty(db: AsyncSession) -> None:
    """list_inventory returns an empty list when the store has no inventory."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)

    entries = await list_inventory(db, store_id=store.id)

    assert entries == []


# ── get_entry ─────────────────────────────────────────────────────────────────


async def test_get_entry_success(db: AsyncSession) -> None:
    """get_entry returns the correct entry when store matches."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)
    created = await create_store_inventory(
        db, store_id=store.id, product_id=product.id, quantity=5.0
    )

    retrieved = await get_entry(db, entry_id=created.id, store_id=store.id)

    assert retrieved.id == created.id
    assert retrieved.quantity == 5.0


async def test_get_entry_wrong_store_raises_not_found(db: AsyncSession) -> None:
    """get_entry raises NotFound when the entry belongs to a different store."""
    org = await create_org(db)
    store_a = await create_store(db, org_id=org.id, name="Store A")
    store_b = await create_store(db, org_id=org.id, name="Store B")
    product = await create_product(db, org_id=org.id)
    entry = await create_store_inventory(db, store_id=store_a.id, product_id=product.id)

    with pytest.raises(NotFound):
        await get_entry(db, entry_id=entry.id, store_id=store_b.id)


async def test_get_entry_unknown_id_raises_not_found(db: AsyncSession) -> None:
    """get_entry raises NotFound for a completely unknown entry ID."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)

    with pytest.raises(NotFound):
        await get_entry(db, entry_id=uuid.uuid4(), store_id=store.id)


# ── update_entry ──────────────────────────────────────────────────────────────


async def test_update_entry_partial(db: AsyncSession) -> None:
    """update_entry only changes the supplied fields."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)
    entry = await create_store_inventory(
        db,
        store_id=store.id,
        product_id=product.id,
        quantity=3.0,
        low_stock_threshold=1.0,
    )

    updated = await update_entry(
        db, entry_id=entry.id, store_id=store.id, quantity=50.0
    )

    assert updated.quantity == 50.0
    assert updated.low_stock_threshold == 1.0  # unchanged


async def test_update_entry_not_found(db: AsyncSession) -> None:
    """update_entry raises NotFound for an unknown entry ID."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)

    with pytest.raises(NotFound):
        await update_entry(db, entry_id=uuid.uuid4(), store_id=store.id, quantity=1.0)


# ── delete_entry ──────────────────────────────────────────────────────────────


async def test_delete_entry_removes_record(db: AsyncSession) -> None:
    """delete_entry removes the entry so it can no longer be retrieved."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)
    entry = await create_store_inventory(db, store_id=store.id, product_id=product.id)

    await delete_entry(db, entry_id=entry.id, store_id=store.id)

    with pytest.raises(NotFound):
        await get_entry(db, entry_id=entry.id, store_id=store.id)


async def test_delete_entry_not_found(db: AsyncSession) -> None:
    """delete_entry raises NotFound for an unknown entry ID."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)

    with pytest.raises(NotFound):
        await delete_entry(db, entry_id=uuid.uuid4(), store_id=store.id)
