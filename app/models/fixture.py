"""Fixture model — a typed, cell-set infrastructure element within a layout version."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.layout_version import LayoutVersion


class FixtureType(str, enum.Enum):
    WALL = "WALL"
    CHECKOUT = "CHECKOUT"
    FRONT_DESK = "FRONT_DESK"
    DOOR = "DOOR"
    PILLAR = "PILLAR"
    RESTROOM = "RESTROOM"
    STORAGE = "STORAGE"
    STAIRS = "STAIRS"


class Fixture(BaseModel):
    """
    Represents a physical infrastructure element within a layout version, defined
    by a type and an arbitrary set of grid cells stored as JSON:
    [{"row": 0, "col": 0}, ...].

    Name is optional — useful for labelling specific instances (e.g. "North Exit").
    """

    __tablename__ = "fixtures"

    layout_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("layout_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fixture_type: Mapped[FixtureType] = mapped_column(
        Enum(FixtureType, native_enum=False, length=20),
        nullable=False,
    )
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cells: Mapped[list] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    layout_version: Mapped["LayoutVersion"] = relationship(
        "LayoutVersion",
        back_populates="fixtures",
    )
