"""Service layer for StoreInventory CRUD operations."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError, NotFound
from app.models.inventory_movement import InventoryMovement, MovementType
from app.models.product import Product
from app.models.store_inventory import StoreInventory

if TYPE_CHECKING:
    from app.store_inventory.schemas import RecordReceiptRequest, RecordSaleRequest


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
    except IntegrityError:
        raise AppError(
            f"Product {product_id} is already stocked in store {store_id}",
            status_code=409,
        )
    # Re-fetch so the product relationship is eagerly loaded in the response.
    return await get_entry(db, entry_id=entry.id, store_id=store_id)


async def list_inventory(
    db: AsyncSession,
    *,
    store_id: uuid.UUID,
    search: str | None = None,
    category: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[StoreInventory], int]:
    """
    Return a paginated, optionally filtered list of inventory entries for a store.

    - ``search`` performs a case-insensitive partial match on product name OR category.
    - ``category`` performs a case-insensitive partial match on product category only.
    - ``page`` / ``page_size`` control the offset-based pagination window.

    Returns a ``(items, total)`` tuple where ``total`` is the number of rows
    matching the provided filters (including ``search``/``category``) before
    pagination.
    """
    if page < 1:
        raise ValueError(f"page must be >= 1, got {page}")
    if page_size < 1:
        raise ValueError(f"page_size must be >= 1, got {page_size}")

    store_filter = [StoreInventory.store_id == store_id]
    product_filters: list = []

    if search:
        term = f"%{search}%"
        product_filters.append(
            or_(
                Product.name.ilike(term),
                Product.category.ilike(term),
            )
        )

    if category:
        product_filters.append(Product.category.ilike(f"%{category}%"))

    needs_join = bool(product_filters)
    all_filters = store_filter + product_filters

    # Count matching rows before pagination.
    # Only JOIN to the products table when product-level predicates are present.
    if needs_join:
        count_stmt = (
            select(func.count(StoreInventory.id))
            .join(Product, StoreInventory.product_id == Product.id)
            .where(*all_filters)
        )
    else:
        count_stmt = select(func.count(StoreInventory.id)).where(*store_filter)
    total: int = (await db.execute(count_stmt)).scalar_one()

    # Fetch the requested page with eagerly loaded product data.
    # The JOIN is omitted when no product-table predicates are active; selectinload
    # handles the product relationship efficiently in both cases.
    if needs_join:
        items_stmt = (
            select(StoreInventory)
            .join(Product, StoreInventory.product_id == Product.id)
            .where(*all_filters)
        )
    else:
        items_stmt = select(StoreInventory).where(*store_filter)
    items_stmt = (
        items_stmt.options(selectinload(StoreInventory.product))
        .order_by(StoreInventory.created_at, StoreInventory.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(items_stmt)
    items = list(result.scalars().all())

    return items, total


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
        select(StoreInventory)
        .where(
            and_(
                StoreInventory.id == entry_id,
                StoreInventory.store_id == store_id,
            )
        )
        .options(selectinload(StoreInventory.product))
        .execution_options(populate_existing=True)
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
    # Re-fetch so the product relationship is eagerly loaded in the response.
    return await get_entry(db, entry_id=entry_id, store_id=store_id)


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


# ── Inventory movements ───────────────────────────────────────────────────────


async def record_receipt(
    db: AsyncSession,
    inventory_id: uuid.UUID,
    data: "RecordReceiptRequest",
    user_id: uuid.UUID,
) -> InventoryMovement:
    """
    Record an inventory receipt and increment the stored quantity.

    Raises NotFound if the inventory entry does not exist.
    """
    stmt = select(StoreInventory).where(StoreInventory.id == inventory_id)
    result = await db.execute(stmt)
    inventory = result.scalars().first()
    if not inventory:
        raise NotFound(f"Inventory entry {inventory_id} not found")

    movement = InventoryMovement(
        store_inventory_id=inventory_id,
        movement_type=MovementType.RECEIPT,
        quantity=data.quantity,
        unit_cost=data.unit_cost,
        reference_number=data.reference_number,
        notes=data.notes,
        performed_by_user_id=user_id,
    )
    db.add(movement)

    inventory.quantity += data.quantity

    await db.flush()
    await db.refresh(movement)
    return movement


async def record_sale(
    db: AsyncSession,
    inventory_id: uuid.UUID,
    data: "RecordSaleRequest",
    user_id: uuid.UUID,
) -> InventoryMovement:
    """
    Record an inventory sale and decrement the stored quantity.

    Raises NotFound if the inventory entry does not exist.
    Raises AppError(400) if the sale quantity exceeds available stock.
    """
    stmt = select(StoreInventory).where(StoreInventory.id == inventory_id)
    result = await db.execute(stmt)
    inventory = result.scalars().first()
    if not inventory:
        raise NotFound(f"Inventory entry {inventory_id} not found")

    if inventory.quantity < data.quantity:
        raise AppError(
            f"Insufficient stock: {inventory.quantity} available, {data.quantity} requested"
        )

    movement = InventoryMovement(
        store_inventory_id=inventory_id,
        movement_type=MovementType.SALE,
        quantity=data.quantity,
        unit_price=data.unit_price,
        reference_number=data.reference_number,
        notes=data.notes,
        performed_by_user_id=user_id,
    )
    db.add(movement)

    inventory.quantity -= data.quantity

    await db.flush()
    await db.refresh(movement)
    return movement
