"""InventoryPlacement model — zone assignment history for a store inventory item."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.store_inventory import StoreInventory
    from app.models.zone import Zone


class InventoryPlacement(BaseModel):
    """
    Records that a store inventory item was placed in a specific zone.

    Only one placement per inventory item may be active at a time
    (``ended_at IS NULL``).  When a new placement is created the previous
    active placement is automatically closed by setting ``ended_at`` to the
    current time.
    """

    __tablename__ = "inventory_placements"

    store_inventory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("store_inventory.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    zone_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("zones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    placed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Relationships
    zone: Mapped["Zone"] = relationship("Zone")
    store_inventory: Mapped["StoreInventory"] = relationship("StoreInventory")

    # ── Computed helpers exposed to Pydantic via from_attributes ──────────────

    @property
    def started_at(self) -> datetime:
        """Alias for created_at — the moment the placement became active."""
        return self.created_at

    @property
    def zone_name(self) -> str:
        """Name of the zone this item was placed in."""
        return self.zone.name

    @property
    def duration_display(self) -> str | None:
        """
        Human-readable duration the item was in this zone.

        Returns ``None`` if the placement is still active (``ended_at`` is
        ``None``).  Otherwise returns a string in the form:
        - ``"2 days, 3 hrs"`` when the duration spans at least one full day
        - ``"1 hr, 45 mins"`` when the duration spans at least one full hour
        - ``"12 mins"`` when the duration is less than one hour
        - ``"< 1 min"`` when the duration is less than one minute
        """
        if self.ended_at is None:
            return None

        delta = self.ended_at - self.created_at
        total_seconds = max(int(delta.total_seconds()), 0)

        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60

        if days > 0:
            day_label = "day" if days == 1 else "days"
            hr_label = "hr" if hours == 1 else "hrs"
            return f"{days} {day_label}, {hours} {hr_label}"

        if hours > 0:
            hr_label = "hr" if hours == 1 else "hrs"
            min_label = "min" if minutes == 1 else "mins"
            return f"{hours} {hr_label}, {minutes} {min_label}"

        if minutes > 0:
            min_label = "min" if minutes == 1 else "mins"
            return f"{minutes} {min_label}"

        return "< 1 min"
