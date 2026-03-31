"""LayoutVersion model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.fixture import Fixture
    from app.models.zone import Zone


class LayoutVersion(BaseModel):
    """Represents a versioned layout configuration for a store grid."""

    __tablename__ = "layout_versions"
    __table_args__ = (
        UniqueConstraint(
            "store_id", "version_number", name="uq_layout_versions_store_version"
        ),
    )

    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    rows: Mapped[int] = mapped_column(Integer, nullable=False)
    cols: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Populated in BE-07 — selectin-loaded so zones are always available on read
    zones: Mapped[list["Zone"]] = relationship(
        "Zone",
        back_populates="layout_version",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    # Populated in BE-08 — selectin-loaded so fixtures are always available on read
    fixtures: Mapped[list["Fixture"]] = relationship(
        "Fixture",
        back_populates="layout_version",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
