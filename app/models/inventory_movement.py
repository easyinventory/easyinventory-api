from __future__ import annotations

import uuid
from decimal import Decimal
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.zone import Zone


class MovementType(PyEnum):
    """Inventory movement type enumeration."""

    RECEIPT = "receipt"
    SALE = "sale"


class InventoryMovement(BaseModel):
    """Record of inventory quantity changes with full audit trail."""

    __tablename__ = "inventory_movements"

    store_inventory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("store_inventory.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    movement_type: Mapped[MovementType] = mapped_column(
        Enum(
            MovementType,
            values_callable=lambda x: [e.value for e in x],
            name="movement_type",
            create_type=False,
        ),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    performed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("zones.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # created_at inherited from BaseModel

    zone: Mapped["Zone | None"] = relationship("Zone", lazy="selectin")

    @property
    def zone_name(self) -> str | None:
        """Name of the zone at the time of this movement, if any."""
        return self.zone.name if self.zone else None
