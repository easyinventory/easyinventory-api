"""Service layer for analytics aggregate queries."""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFound
from app.models.fixture import Fixture
from app.models.inventory_placement import InventoryPlacement
from app.models.layout_version import LayoutVersion
from app.models.store_inventory import StoreInventory
from app.models.zone import Zone
from app.analytics.schemas import (
    CellSchema,
    FixtureSummary,
    StockStatus,
    UnzonedSummary,
    ZoneInventoryItem,
    ZoneInventorySummary,
    ZoneInventorySummaryResponse,
)


def _classify_stock(quantity: float, threshold: float | None) -> StockStatus:
    """Determine stock health status for a single inventory item."""
    if quantity <= 0:
        return StockStatus.OUT
    if threshold is not None and quantity <= threshold:
        return StockStatus.LOW
    return StockStatus.OK


async def get_zone_inventory_summary(
    db: AsyncSession,
    store_id: uuid.UUID,
) -> ZoneInventorySummaryResponse:
    """
    Build the zone-level inventory heatmap data for a store.

    Fetches the active layout, all zones/fixtures, and all inventory items
    with their active placements in two queries. Returns aggregated per-zone
    inventory statistics plus an unzoned summary.

    Raises :class:`NotFound` if the store has no active layout version.
    """
    # ── 1. Get active layout with zones and fixtures ──────────────────────
    layout_result = await db.execute(
        select(LayoutVersion)
        .where(
            and_(
                LayoutVersion.store_id == store_id,
                LayoutVersion.is_active.is_(True),
            )
        )
        .options(
            selectinload(LayoutVersion.zones),
            selectinload(LayoutVersion.fixtures),
        )
    )
    layout = layout_result.scalar_one_or_none()
    if layout is None:
        raise NotFound(f"No active layout version found for store {store_id}")

    # Build zone lookup: zone_id → Zone ORM object
    zone_map: dict[uuid.UUID, Zone] = {z.id: z for z in layout.zones}

    # ── 2. Get all inventory items with their active placements ───────────
    # LEFT JOIN so we also capture items with no active placement (unzoned).
    inv_result = await db.execute(
        select(StoreInventory, InventoryPlacement.zone_id)
        .outerjoin(
            InventoryPlacement,
            and_(
                InventoryPlacement.store_inventory_id == StoreInventory.id,
                InventoryPlacement.ended_at.is_(None),
            ),
        )
        .where(StoreInventory.store_id == store_id)
        .options(selectinload(StoreInventory.product))
    )

    # ── 3. Group items by zone ────────────────────────────────────────────
    zoned_items: dict[uuid.UUID, list[StoreInventory]] = defaultdict(list)
    unzoned_items: list[StoreInventory] = []

    for inv, zone_id in inv_result.all():
        if zone_id and zone_id in zone_map:
            zoned_items[zone_id].append(inv)
        else:
            unzoned_items.append(inv)

    # ── 4. Build per-zone summaries ───────────────────────────────────────
    zone_summaries: list[ZoneInventorySummary] = []

    for zone in layout.zones:
        items = zoned_items.get(zone.id, [])
        zone_inv_items: list[ZoneInventoryItem] = []
        low_count = 0
        out_count = 0
        total_qty: float = 0

        for inv in items:
            status = _classify_stock(inv.quantity, inv.low_stock_threshold)
            if status == StockStatus.LOW:
                low_count += 1
            elif status == StockStatus.OUT:
                out_count += 1
            total_qty += inv.quantity

            zone_inv_items.append(
                ZoneInventoryItem(
                    inventory_id=inv.id,
                    product_name=inv.product.name,
                    sku=inv.product.sku,
                    category=inv.product.category,
                    quantity=inv.quantity,
                    low_stock_threshold=inv.low_stock_threshold,
                    unit_price=str(inv.unit_price) if inv.unit_price else None,
                    stock_status=status,
                )
            )

        zone_summaries.append(
            ZoneInventorySummary(
                zone_id=zone.id,
                zone_name=zone.name,
                zone_color=zone.color,
                cells=[CellSchema(row=c["row"], col=c["col"]) for c in zone.cells],
                total_items=len(items),
                total_quantity=total_qty,
                low_stock_count=low_count,
                out_of_stock_count=out_count,
                items=zone_inv_items,
            )
        )

    # ── 5. Build fixture summaries ────────────────────────────────────────
    fixture_summaries: list[FixtureSummary] = [
        FixtureSummary(
            fixture_id=f.id,
            fixture_name=f.name or f.fixture_type.value,
            fixture_type=(
                f.fixture_type.value
                if hasattr(f.fixture_type, "value")
                else str(f.fixture_type)
            ),
            cells=[CellSchema(row=c["row"], col=c["col"]) for c in f.cells],
        )
        for f in layout.fixtures
    ]

    # ── 6. Build unzoned summary ──────────────────────────────────────────
    unzoned_low = 0
    unzoned_out = 0
    unzoned_qty: float = 0
    for inv in unzoned_items:
        status = _classify_stock(inv.quantity, inv.low_stock_threshold)
        if status == StockStatus.LOW:
            unzoned_low += 1
        elif status == StockStatus.OUT:
            unzoned_out += 1
        unzoned_qty += inv.quantity

    # ── 7. Assemble response ──────────────────────────────────────────────
    return ZoneInventorySummaryResponse(
        layout_id=layout.id,
        layout_version=layout.version_number,
        rows=layout.rows,
        cols=layout.cols,
        zones=zone_summaries,
        fixtures=fixture_summaries,
        unzoned_summary=UnzonedSummary(
            total_items=len(unzoned_items),
            total_quantity=unzoned_qty,
            low_stock_count=unzoned_low,
            out_of_stock_count=unzoned_out,
        ),
    )
