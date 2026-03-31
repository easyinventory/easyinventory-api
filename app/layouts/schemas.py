"""Pydantic schemas for LayoutVersion."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.zones.schemas import ZoneRead


class LayoutVersionCreate(BaseModel):
    """Payload for creating a new layout version."""

    rows: int = Field(..., ge=2, le=30, description="Number of rows (2–30)")
    cols: int = Field(..., ge=2, le=30, description="Number of columns (2–30)")


class LayoutVersionRead(BaseModel):
    """Full representation of a layout version returned from the API."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    store_id: uuid.UUID
    version_number: int
    rows: int
    cols: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    zones: list[ZoneRead] = Field(default_factory=list)
    # fixtures populated in BE-08
    fixtures: list = Field(default_factory=list)
