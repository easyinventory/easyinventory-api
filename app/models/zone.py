"""Zone model — a named, coloured cell-set within a layout version grid."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.layout_version import LayoutVersion


class Zone(BaseModel):
    """
    Represents a named area within a layout version, defined by an arbitrary
    set of grid cells stored as JSON: [{"row": 0, "col": 0}, ...].
    """

    __tablename__ = "zones"

    layout_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("layout_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Hex colour code, e.g. "#FF5733"
    color: Mapped[str] = mapped_column(String(7), nullable=False)
    # Cell positions: [{"row": int, "col": int}, ...]
    cells: Mapped[list] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    layout_version: Mapped["LayoutVersion"] = relationship(
        "LayoutVersion",
        back_populates="zones",
    )
