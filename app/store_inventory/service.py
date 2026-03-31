"""Service layer for StoreInventory CRUD operations."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFound
from app.models.product import Product
from app.models.store_inventory import StoreInventory


async def add_product(
    db: AsyncSession,
    *,
    store_id: uuid.UUID,
    org_id: uuid.UUID,
    product_id: uuid.UUID,
    quantity: float = 0.0,
    unit_price: Decimal | None = None,
    low_stock_threshold: float | None = None,
) -> StoreInventory:
    """
    Add a product to a store's inventory.

    Raises NotFound if the product does not exist in the org (tenant isolation).
    Raises 409 AppError if the product is already stocked in the store.
    """
    # Validate the product belongs to the same org as the store.
    product_result = await db.execute(
        select(Product).where(and_(Product.id == product_id, Product.org_id == org_id))
    )
    if product_result.scalar_one_or_none() is None:
        raise NotFound(f"Product {product_id} not found in organization {org_id}")

    # Pre-check for duplicates (common case — not concurrency-safe alone).
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
    # Catch unique-constraint violation from concurrent inserts and surface as 409.
    try:
        await db.flush()
        await db.refresh(entry)
    except IntegrityError:
        raise AppError(
            f"Product {product_id} is already stocked in store {store_id}",
            status_code=409,
        )
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


# Sentinel that distinguishes "argument not provided" from "explicitly set to None".
# This allows clients to clear nullable fields (e.g. unit_price, low_stock_threshold)
# by sending {"unit_price": null} in a PATCH request.
_UNSET = object()


async def update_entry(
    db: AsyncSession,
    *,
    entry_id: uuid.UUID,
    store_id: uuid.UUID,
    quantity: float | None | object = _UNSET,
    unit_price: Decimal | None | object = _UNSET,
    low_stock_threshold: float | None | object = _UNSET,
) -> StoreInventory:
    """
    Partially update an inventory entry.

    Only fields explicitly provided are changed. Fields explicitly set to None
    will be cleared when the underlying column is nullable.
    Raises NotFound if the entry does not exist.
    """
    entry = await get_entry(db, entry_id=entry_id, store_id=store_id)

    if quantity is not _UNSET:
        entry.quantity = quantity  # type: ignore[assignment]
    if unit_price is not _UNSET:
        entry.unit_price = unit_price  # type: ignore[assignment]
    if low_stock_threshold is not _UNSET:
        entry.low_stock_threshold = low_stock_threshold  # type: ignore[assignment]

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
