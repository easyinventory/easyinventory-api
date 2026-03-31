"""Pydantic schemas for Zone."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class CellPosition(BaseModel):
    """A single grid cell identified by its zero-based row and column indices."""

    row: int = Field(..., ge=0, description="Zero-based row index")
    col: int = Field(..., ge=0, description="Zero-based column index")


class ZoneCreate(BaseModel):
    """Payload for creating a new zone."""

    name: str = Field(..., min_length=1, max_length=100)
    color: str = Field(
        ..., pattern=r"^#[0-9A-Fa-f]{6}$", description="Hex colour, e.g. #FF5733"
    )
    cells: list[CellPosition] = Field(
        ..., min_length=1, description="At least 1 cell required"
    )

    @field_validator("cells")
    @classmethod
    def no_duplicate_cells(cls, v: list[CellPosition]) -> list[CellPosition]:
        """Reject duplicate (row, col) pairs within a single zone."""
        seen: set[tuple[int, int]] = set()
        for cell in v:
            key = (cell.row, cell.col)
            if key in seen:
                raise ValueError(f"Duplicate cell ({cell.row}, {cell.col}) in zone")
            seen.add(key)
        return v


class ZoneUpdate(BaseModel):
    """Payload for partially updating a zone. All fields are optional."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    cells: Optional[list[CellPosition]] = Field(None, min_length=1)

    @field_validator("cells")
    @classmethod
    def no_duplicate_cells(
        cls, v: Optional[list[CellPosition]]
    ) -> Optional[list[CellPosition]]:
        """Reject duplicate (row, col) pairs within a single zone."""
        if v is None:
            return v
        seen: set[tuple[int, int]] = set()
        for cell in v:
            key = (cell.row, cell.col)
            if key in seen:
                raise ValueError(f"Duplicate cell ({cell.row}, {cell.col}) in zone")
            seen.add(key)
        return v


class ZoneRead(BaseModel):
    """Full representation of a zone returned from the API."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    layout_version_id: uuid.UUID
    name: str
    color: str
    cells: list[CellPosition]
    created_at: datetime
    updated_at: datetime
