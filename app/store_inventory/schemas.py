from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum

from pydantic import BaseModel, Field


class StoreInventoryCreate(BaseModel):
    product_id: uuid.UUID
    quantity: float = Field(default=0.0, ge=0, description="Units in stock")
    unit_price: Decimal | None = Field(
        default=None, description="Per-unit price (optional)"
    )
    low_stock_threshold: float | None = Field(
        default=None,
        ge=0,
        description="Alert threshold for low stock (optional)",
    )


class StoreInventoryUpdate(BaseModel):
    quantity: float | None = Field(default=None, ge=0)
    unit_price: Decimal | None = None
    low_stock_threshold: float | None = Field(default=None, ge=0)


class ProductSummary(BaseModel):
    """Minimal product fields embedded in inventory responses."""

    id: uuid.UUID
    name: str
    sku: str | None
    category: str | None
    description: str | None

    model_config = {"from_attributes": True}


class StoreInventoryRead(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    product_id: uuid.UUID
    quantity: float
    unit_price: Decimal | None
    low_stock_threshold: float | None
    created_at: datetime
    updated_at: datetime
    product: ProductSummary

    model_config = {"from_attributes": True}


class PaginatedInventoryResponse(BaseModel):
    """Paginated wrapper for inventory list responses."""

    items: list[StoreInventoryRead]
    total: int
    page: int
    page_size: int


# ── Movement schemas ──────────────────────────────────────────────────────────


class MovementTypeEnum(str, PyEnum):
    """Movement type for API responses."""

    RECEIPT = "receipt"
    SALE = "sale"


class RecordReceiptRequest(BaseModel):
    """Request to record an inventory receipt."""

    quantity: int = Field(..., gt=0, description="Quantity received")
    unit_cost: Decimal | None = Field(None, description="Unit cost per item")
    reference_number: str | None = Field(None, max_length=100)
    notes: str | None = Field(None, description="Receipt notes")


class RecordSaleRequest(BaseModel):
    """Request to record an inventory sale."""

    quantity: int = Field(..., gt=0, description="Quantity sold")
    unit_price: Decimal | None = Field(None, description="Unit price per item")
    reference_number: str | None = Field(None, max_length=100)
    notes: str | None = Field(None, description="Sale notes")


class MovementRead(BaseModel):
    """Schema for reading inventory movement records."""

    id: uuid.UUID
    store_inventory_id: uuid.UUID
    movement_type: MovementTypeEnum
    quantity: int
    unit_cost: Decimal | None
    unit_price: Decimal | None
    reference_number: str | None
    notes: str | None
    performed_by_user_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Placement schemas ─────────────────────────────────────────────────────────


class AssignZoneRequest(BaseModel):
    """Request body for PATCH …/placements — assign an inventory item to a zone."""

    active_zone_id: uuid.UUID


class PlacementRead(BaseModel):
    """
    Schema for reading an inventory placement record.

    ``zone_name`` and ``duration_display`` are computed properties on the ORM
    model and are surfaced here via ``from_attributes = True``.
    """

    id: uuid.UUID
    store_inventory_id: uuid.UUID
    zone_id: uuid.UUID
    zone_name: str
    started_at: datetime
    ended_at: datetime | None
    placed_by_user_id: uuid.UUID
    duration_display: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
