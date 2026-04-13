from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.roles import OrgRole
from app.models.org_membership import OrgMembership
from app.models.store import Store
from app.models.inventory_movement import InventoryMovement
from app.models.inventory_placement import InventoryPlacement
from app.orgs.deps import RequireOrgRole, get_current_org_membership
from app.stores.deps import get_store_from_path
from app.store_inventory.schemas import (
    AssignZoneRequest,
    MovementRead,
    PaginatedInventoryResponse,
    PlacementRead,
    RecordReceiptRequest,
    RecordSaleRequest,
    StoreInventoryCreate,
    StoreInventoryRead,
    StoreInventoryUpdate,
)
from app.store_inventory.service import (
    add_product,
    assign_zone,
    delete_entry,
    get_entry,
    get_placement_history,
    list_inventory,
    list_movements,
    record_receipt,
    record_sale,
    remove_from_zone,
    update_entry,
)
from app.models.store_inventory import StoreInventory

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
) -> StoreInventory:
    """Add a product to this store's inventory."""
    entry = await add_product(
        db,
        store_id=store.id,
        org_id=store.org_id,
        product_id=data.product_id,
        quantity=data.quantity,
        unit_price=data.unit_price,
        low_stock_threshold=data.low_stock_threshold,
    )
    await db.commit()
    return entry


@router.get("", response_model=PaginatedInventoryResponse)
async def get_store_inventory(
    store: Store = Depends(get_store_from_path),
    db: AsyncSession = Depends(get_db),
    search: str | None = Query(
        default=None,
        description="Case-insensitive partial match on product name or category.",
    ),
    category: str | None = Query(
        default=None,
        description="Case-insensitive partial match on product category.",
    ),
    page: int = Query(default=1, ge=1, description="1-based page number."),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page."),
    paginated: bool = Query(default=True, description="is the page paginated."),
) -> PaginatedInventoryResponse:
    """List inventory entries for this store with optional search, category filter, and pagination."""
    items, total = await list_inventory(
        db,
        store_id=store.id,
        search=search,
        category=category,
        page=page,
        page_size=page_size,
    )
    return PaginatedInventoryResponse(
        items=[StoreInventoryRead.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{entry_id}", response_model=StoreInventoryRead)
async def get_inventory_entry(
    entry_id: uuid.UUID,
    store: Store = Depends(get_store_from_path),
    db: AsyncSession = Depends(get_db),
) -> StoreInventory:
    """Get a single inventory entry."""
    return await get_entry(db, entry_id=entry_id, store_id=store.id)


@router.patch("/{entry_id}", response_model=StoreInventoryRead)
async def update_inventory_entry(
    entry_id: uuid.UUID,
    data: StoreInventoryUpdate,
    store: Store = Depends(get_store_from_path),
    db: AsyncSession = Depends(get_db),
) -> StoreInventory:
    """Partially update an inventory entry."""
    entry = await update_entry(
        db,
        entry_id=entry_id,
        store_id=store.id,
        **{k: v for k, v in data.model_dump().items() if k in data.model_fields_set},
    )
    await db.commit()
    return entry


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


@router.post("/{inventory_id}/receipts", response_model=MovementRead, status_code=201)
async def record_inventory_receipt(
    inventory_id: uuid.UUID,
    data: RecordReceiptRequest,
    store: Store = Depends(get_store_from_path),
    db: AsyncSession = Depends(get_db),
    membership: OrgMembership = Depends(get_current_org_membership),
) -> InventoryMovement:
    """Record an inventory receipt (incoming stock)."""
    movement = await record_receipt(
        db, inventory_id, store.id, data, membership.user_id
    )
    await db.commit()
    return movement


@router.get("/{inventory_id}/movements", response_model=list[MovementRead])
async def list_inventory_movements(
    inventory_id: uuid.UUID,
    store: Store = Depends(get_store_from_path),
    db: AsyncSession = Depends(get_db),
) -> list[InventoryMovement]:
    """Return the full stock-movement history for an inventory item, newest first."""
    return await list_movements(db, inventory_id, store.id)


@router.post("/{inventory_id}/sales", response_model=MovementRead, status_code=201)
async def record_inventory_sale(
    inventory_id: uuid.UUID,
    data: RecordSaleRequest,
    store: Store = Depends(get_store_from_path),
    db: AsyncSession = Depends(get_db),
    membership: OrgMembership = Depends(get_current_org_membership),
) -> InventoryMovement:
    """Record an inventory sale (outgoing stock)."""
    movement = await record_sale(db, inventory_id, store.id, data, membership.user_id)
    await db.commit()
    return movement


# ── Placement endpoints ──────────────────────────────────────────────────────


@router.patch(
    "/{inventory_id}/placements",
    response_model=PlacementRead,
    status_code=status.HTTP_201_CREATED,
)
async def assign_inventory_to_zone(
    inventory_id: uuid.UUID,
    data: AssignZoneRequest,
    store: Store = Depends(get_store_from_path),
    db: AsyncSession = Depends(get_db),
    membership: OrgMembership = Depends(get_current_org_membership),
) -> InventoryPlacement:
    """
    Assign an inventory item to a zone.

    Creates a new placement and automatically closes the previous active
    placement (if any).  The zone must belong to one of the store's layout
    versions.
    """
    placement = await assign_zone(
        db, inventory_id, store.id, data.active_zone_id, membership.user_id
    )
    await db.commit()
    return placement


@router.get("/{inventory_id}/placements", response_model=list[PlacementRead])
async def list_placement_history(
    inventory_id: uuid.UUID,
    store: Store = Depends(get_store_from_path),
    db: AsyncSession = Depends(get_db),
) -> list[InventoryPlacement]:
    """Return the full zone-placement history for an inventory item, newest first."""
    return await get_placement_history(db, inventory_id, store.id)


@router.delete(
    "/{inventory_id}/placements/current",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_inventory_from_zone(
    inventory_id: uuid.UUID,
    store: Store = Depends(get_store_from_path),
    db: AsyncSession = Depends(get_db),
    _membership: OrgMembership = Depends(get_current_org_membership),
) -> None:
    """Remove an inventory item from its current zone."""
    await remove_from_zone(db, inventory_id, store.id)
    await db.commit()
