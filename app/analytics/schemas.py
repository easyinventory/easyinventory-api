"""Pydantic schemas for analytics responses."""

from __future__ import annotations

import uuid
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, computed_field

# ── Shared cell schema ────────────────────────────────────────────────────────


class CellSchema(BaseModel):
    """A single grid cell coordinate."""

    row: int
    col: int


# ── Stock status enum ─────────────────────────────────────────────────────────


class StockStatus(str, Enum):
    """Stock health classification for an inventory item."""

    OK = "ok"
    LOW = "low"
    OUT = "out"


# ── Zone inventory summary ────────────────────────────────────────────────────


class ZoneInventoryItem(BaseModel):
    """A single inventory item within a zone, with stock health info."""

    inventory_id: uuid.UUID
    product_name: str
    sku: str | None = None
    category: str | None = None
    quantity: float
    low_stock_threshold: float | None = None
    unit_price: Decimal | None = None
    stock_status: StockStatus


class ZoneInventorySummary(BaseModel):
    """Per-zone aggregate inventory data for the heatmap."""

    zone_id: uuid.UUID
    zone_name: str
    zone_color: str
    cells: list[CellSchema]
    total_items: int = 0
    total_quantity: float = 0
    low_stock_count: int = 0
    out_of_stock_count: int = 0
    items: list[ZoneInventoryItem] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def health_ratio(self) -> float:
        """0.0 = all healthy, 1.0 = all items have stock issues.

        Used by the frontend to compute heatmap color intensity.
        """
        if self.total_items == 0:
            return 0.0
        return (self.low_stock_count + self.out_of_stock_count) / self.total_items


class FixtureSummary(BaseModel):
    """Minimal fixture info for rendering non-interactive heatmap cells."""

    fixture_id: uuid.UUID
    fixture_name: str
    fixture_type: str
    cells: list[CellSchema]


class UnzonedSummary(BaseModel):
    """Aggregate for inventory items not assigned to any zone."""

    total_items: int = 0
    total_quantity: float = 0
    low_stock_count: int = 0
    out_of_stock_count: int = 0


class ZoneInventorySummaryResponse(BaseModel):
    """Top-level response for the zone inventory summary endpoint."""

    layout_id: uuid.UUID
    layout_version: int
    rows: int
    cols: int
    zones: list[ZoneInventorySummary]
    fixtures: list[FixtureSummary]
    unzoned_summary: UnzonedSummary
