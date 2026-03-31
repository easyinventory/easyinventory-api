"""Service layer for StoreInventory CRUD operations."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFound
from app.models.store_inventory import StoreInventory


async def add_product(
    db: AsyncSession,
    *,
    store_id: uuid.UUID,
    product_id: uuid.UUID,
    quantity: float = 0.0,
    unit_price: Decimal | None = None,
    low_stock_threshold: float | None = None,
) -> StoreInventory:
    """
    Add a product to a store's inventory.

    Raises 409 AppError if the product is already stocked in the store.
    """
    existing = await db.execute(
        select(StoreInventory).where(
            and_(
                StoreInventory.store_id == store_id,
                StoreInventory.product_id == product_id,
            )
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise AppError(
            f"Product {product_id} is already stocked in store {store_id}",
            status_code=409,
        )

    entry = StoreInventory(
        store_id=store_id,
        product_id=product_id,
        quantity=quantity,
        unit_price=unit_price,
        low_stock_threshold=low_stock_threshold,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


async def list_inventory(
    db: AsyncSession,
    *,
    store_id: uuid.UUID,
) -> list[StoreInventory]:
    """Return all inventory entries for a store, ordered by creation time."""
    stmt = (
        select(StoreInventory)
        .where(StoreInventory.store_id == store_id)
        .order_by(StoreInventory.created_at)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_entry(
    db: AsyncSession,
    *,
    entry_id: uuid.UUID,
    store_id: uuid.UUID,
) -> StoreInventory:
    """
    Get a single inventory entry by ID, scoped to the given store.

    Raises NotFound if the entry does not exist or belongs to a different store.
    """
    result = await db.execute(
        select(StoreInventory).where(
            and_(
                StoreInventory.id == entry_id,
                StoreInventory.store_id == store_id,
            )
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise NotFound(f"Inventory entry {entry_id} not found in store {store_id}")
    return entry


async def update_entry(
    db: AsyncSession,
    *,
    entry_id: uuid.UUID,
    store_id: uuid.UUID,
    quantity: float | None = None,
    unit_price: Decimal | None = None,
    low_stock_threshold: float | None = None,
) -> StoreInventory:
    """
    Partially update an inventory entry.

    Only fields explicitly provided (not None) are changed.
    Raises NotFound if the entry does not exist.
    """
    entry = await get_entry(db, entry_id=entry_id, store_id=store_id)

    if quantity is not None:
        entry.quantity = quantity
    if unit_price is not None:
        entry.unit_price = unit_price
    if low_stock_threshold is not None:
        entry.low_stock_threshold = low_stock_threshold

    await db.flush()
    await db.refresh(entry)
    return entry


async def delete_entry(
    db: AsyncSession,
    *,
    entry_id: uuid.UUID,
    store_id: uuid.UUID,
) -> None:
    """
    Delete an inventory entry.

    Raises NotFound if the entry does not exist or belongs to a different store.
    """
    entry = await get_entry(db, entry_id=entry_id, store_id=store_id)
    await db.delete(entry)
    await db.flush()
