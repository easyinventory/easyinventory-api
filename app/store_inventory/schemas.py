from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class StoreInventoryCreate(BaseModel):
    product_id: uuid.UUID
    quantity: float = Field(default=0.0, ge=0, description="Units in stock")
    unit_price: Decimal | None = Field(
        default=None, description="Per-unit price (optional)"
    )
    low_stock_threshold: float | None = Field(
        default=None, description="Alert threshold for low stock (optional)"
    )


class StoreInventoryUpdate(BaseModel):
    quantity: float | None = Field(default=None, ge=0)
    unit_price: Decimal | None = None
    low_stock_threshold: float | None = None


class StoreInventoryRead(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    product_id: uuid.UUID
    quantity: float
    unit_price: Decimal | None
    low_stock_threshold: float | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
