from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class StoreCreate(BaseModel):
    """Schema for creating a new store."""

    name: str = Field(..., min_length=1, max_length=255, description="Store name")


class StoreRead(BaseModel):
    """Schema for reading store data."""

    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
