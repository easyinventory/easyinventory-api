"""Routes for analytics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.store import Store
from app.stores.deps import get_store_from_path
from app.analytics.schemas import ZoneInventorySummaryResponse
from app.analytics import service

router = APIRouter(prefix="/api/stores/{store_id}/analytics", tags=["analytics"])


@router.get(
    "/zone-inventory-summary",
    response_model=ZoneInventorySummaryResponse,
)
async def get_zone_inventory_summary(
    store: Store = Depends(get_store_from_path),
    db: AsyncSession = Depends(get_db),
) -> ZoneInventorySummaryResponse:
    """
    Return per-zone inventory stock data for the store's active layout.

    Powers the Inventory Heatmap view — each zone includes aggregate stock
    counts, a health ratio, and a list of individual inventory items with
    their current stock status.
    """
    return await service.get_zone_inventory_summary(db, store.id)
