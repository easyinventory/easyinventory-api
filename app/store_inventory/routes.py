from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.roles import OrgRole
from app.models.org_membership import OrgMembership
from app.models.store import Store
from app.orgs.deps import RequireOrgRole, get_current_org_membership
from app.stores.deps import get_store_from_path
from app.store_inventory.schemas import (
    StoreInventoryCreate,
    StoreInventoryRead,
    StoreInventoryUpdate,
)
from app.store_inventory.service import (
    add_product,
    delete_entry,
    get_entry,
    list_inventory,
    update_entry,
)

router = APIRouter(prefix="/api/stores/{store_id}/inventory", tags=["store-inventory"])


@router.post(
    "",
    response_model=StoreInventoryRead,
    status_code=status.HTTP_201_CREATED,
)
async def stock_product(
    data: StoreInventoryCreate,
    store: Store = Depends(get_store_from_path),
    db: AsyncSession = Depends(get_db),
) -> StoreInventoryRead:
    """Add a product to this store's inventory."""
    entry = await add_product(
        db,
        store_id=store.id,
        product_id=data.product_id,
        quantity=data.quantity,
        unit_price=data.unit_price,
        low_stock_threshold=data.low_stock_threshold,
    )
    await db.commit()
    return StoreInventoryRead.model_validate(entry)


@router.get("", response_model=list[StoreInventoryRead])
async def get_store_inventory(
    store: Store = Depends(get_store_from_path),
    db: AsyncSession = Depends(get_db),
) -> list[StoreInventoryRead]:
    """List all inventory entries for this store."""
    entries = await list_inventory(db, store_id=store.id)
    return [StoreInventoryRead.model_validate(e) for e in entries]


@router.get("/{entry_id}", response_model=StoreInventoryRead)
async def get_inventory_entry(
    entry_id: uuid.UUID,
    store: Store = Depends(get_store_from_path),
    db: AsyncSession = Depends(get_db),
) -> StoreInventoryRead:
    """Get a single inventory entry."""
    entry = await get_entry(db, entry_id=entry_id, store_id=store.id)
    return StoreInventoryRead.model_validate(entry)


@router.patch("/{entry_id}", response_model=StoreInventoryRead)
async def update_inventory_entry(
    entry_id: uuid.UUID,
    data: StoreInventoryUpdate,
    store: Store = Depends(get_store_from_path),
    db: AsyncSession = Depends(get_db),
) -> StoreInventoryRead:
    """Partially update an inventory entry."""
    entry = await update_entry(
        db,
        entry_id=entry_id,
        store_id=store.id,
        quantity=data.quantity,
        unit_price=data.unit_price,
        low_stock_threshold=data.low_stock_threshold,
    )
    await db.commit()
    return StoreInventoryRead.model_validate(entry)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_inventory_entry(
    entry_id: uuid.UUID,
    store: Store = Depends(get_store_from_path),
    _membership: OrgMembership = Depends(RequireOrgRole(OrgRole.OWNER)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an inventory entry. Owner role required."""
    await delete_entry(db, entry_id=entry_id, store_id=store.id)
    await db.commit()
