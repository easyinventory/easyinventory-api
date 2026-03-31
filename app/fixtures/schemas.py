"""Pydantic schemas for Fixture."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.fixture import FixtureType
from app.zones.schemas import CellPosition


class FixtureCreate(BaseModel):
    fixture_type: FixtureType
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    cells: list[CellPosition] = Field(..., min_length=1)

    @field_validator("cells")
    @classmethod
    def no_duplicate_cells(cls, v: list[CellPosition]) -> list[CellPosition]:
        seen: set[tuple[int, int]] = set()
        for cell in v:
            key = (cell.row, cell.col)
            if key in seen:
                raise ValueError(f"Duplicate cell ({cell.row}, {cell.col}) in fixture")
            seen.add(key)
        return v


class FixtureUpdate(BaseModel):
    fixture_type: Optional[FixtureType] = None
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    cells: Optional[list[CellPosition]] = Field(None, min_length=1)

    @field_validator("cells")
    @classmethod
    def no_duplicate_cells(cls, v: Optional[list[CellPosition]]) -> Optional[list[CellPosition]]:
        if v is None:
            return v
        seen: set[tuple[int, int]] = set()
        for cell in v:
            key = (cell.row, cell.col)
            if key in seen:
                raise ValueError(f"Duplicate cell ({cell.row}, {cell.col}) in fixture")
            seen.add(key)
        return v


class FixtureRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    layout_version_id: uuid.UUID
    fixture_type: FixtureType
    name: Optional[str]
    cells: list[CellPosition]
    created_at: datetime
    updated_at: datetime
