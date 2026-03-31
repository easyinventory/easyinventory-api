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

    items, total = await list_inventory(db, store_id=store.id)

    assert total == 2
    assert len(items) == 2
    product_ids = {e.product_id for e in items}
    assert product_ids == {product_a.id, product_b.id}


async def test_list_inventory_scoped_to_store(db: AsyncSession) -> None:
    """list_inventory does not return entries from other stores."""
    org = await create_org(db)
    store_a = await create_store(db, org_id=org.id, name="Store A")
    store_b = await create_store(db, org_id=org.id, name="Store B")
    product = await create_product(db, org_id=org.id)

    await create_store_inventory(db, store_id=store_b.id, product_id=product.id)

    items, total = await list_inventory(db, store_id=store_a.id)

    assert items == []
    assert total == 0


async def test_list_inventory_empty(db: AsyncSession) -> None:
    """list_inventory returns an empty list when the store has no inventory."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)

    items, total = await list_inventory(db, store_id=store.id)

    assert items == []
    assert total == 0


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


# ── list_inventory: product field ─────────────────────────────────────────────


async def test_list_inventory_product_field_populated(db: AsyncSession) -> None:
    """list_inventory eagerly loads the product relationship on each entry."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)
    product = await create_product(
        db, org_id=org.id, name="Widget", category="Hardware", sku="W-001"
    )
    await create_store_inventory(db, store_id=store.id, product_id=product.id)

    items, _ = await list_inventory(db, store_id=store.id)

    assert len(items) == 1
    assert items[0].product is not None
    assert items[0].product.name == "Widget"
    assert items[0].product.category == "Hardware"
    assert items[0].product.sku == "W-001"


# ── list_inventory: search ────────────────────────────────────────────────────


async def test_list_inventory_search_by_product_name(db: AsyncSession) -> None:
    """search= filters entries whose product name matches (case-insensitive)."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)
    widget = await create_product(db, org_id=org.id, name="Blue Widget")
    gadget = await create_product(db, org_id=org.id, name="Red Gadget")
    await create_store_inventory(db, store_id=store.id, product_id=widget.id)
    await create_store_inventory(db, store_id=store.id, product_id=gadget.id)

    items, total = await list_inventory(db, store_id=store.id, search="widget")

    assert total == 1
    assert items[0].product_id == widget.id


async def test_list_inventory_search_by_product_category(db: AsyncSession) -> None:
    """search= also matches against product category."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)
    tool = await create_product(db, org_id=org.id, name="Hammer", category="Tools")
    snack = await create_product(db, org_id=org.id, name="Chips", category="Food")
    await create_store_inventory(db, store_id=store.id, product_id=tool.id)
    await create_store_inventory(db, store_id=store.id, product_id=snack.id)

    items, total = await list_inventory(db, store_id=store.id, search="tools")

    assert total == 1
    assert items[0].product_id == tool.id


async def test_list_inventory_search_no_match_returns_empty(db: AsyncSession) -> None:
    """search= with no matching products returns an empty result."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id, name="Anvil")
    await create_store_inventory(db, store_id=store.id, product_id=product.id)

    items, total = await list_inventory(db, store_id=store.id, search="zzznomatch")

    assert total == 0
    assert items == []


# ── list_inventory: category filter ──────────────────────────────────────────


async def test_list_inventory_category_filter(db: AsyncSession) -> None:
    """category= filters entries to only those whose product category matches."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)
    hardware = await create_product(db, org_id=org.id, name="Bolt", category="Hardware")
    food = await create_product(db, org_id=org.id, name="Bread", category="Food")
    await create_store_inventory(db, store_id=store.id, product_id=hardware.id)
    await create_store_inventory(db, store_id=store.id, product_id=food.id)

    items, total = await list_inventory(db, store_id=store.id, category="hardware")

    assert total == 1
    assert items[0].product_id == hardware.id


# ── list_inventory: pagination ────────────────────────────────────────────────


async def test_list_inventory_pagination_page_size(db: AsyncSession) -> None:
    """page_size= limits the number of returned items."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)
    products = [
        await create_product(db, org_id=org.id, name=f"Product {i}") for i in range(5)
    ]
    for p in products:
        await create_store_inventory(db, store_id=store.id, product_id=p.id)

    items, total = await list_inventory(db, store_id=store.id, page=1, page_size=2)

    assert total == 5  # total reflects all matching rows
    assert len(items) == 2


async def test_list_inventory_pagination_second_page(db: AsyncSession) -> None:
    """page=2 with page_size=2 returns the third and fourth items."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)
    products = [
        await create_product(db, org_id=org.id, name=f"Item {i:02d}") for i in range(4)
    ]
    for p in products:
        await create_store_inventory(db, store_id=store.id, product_id=p.id)

    first_page, _ = await list_inventory(db, store_id=store.id, page=1, page_size=2)
    second_page, _ = await list_inventory(db, store_id=store.id, page=2, page_size=2)

    first_ids = {e.id for e in first_page}
    second_ids = {e.id for e in second_page}
    assert first_ids.isdisjoint(second_ids)  # no overlap between pages
    assert len(second_page) == 2


async def test_list_inventory_pagination_beyond_last_page(db: AsyncSession) -> None:
    """Requesting a page beyond the last returns empty items with correct total."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)
    await create_store_inventory(db, store_id=store.id, product_id=product.id)

    items, total = await list_inventory(db, store_id=store.id, page=999, page_size=20)

    assert total == 1
    assert items == []
