from __future__ import annotations

import uuid
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


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
        Enum(MovementType, name="movement_type"),
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
    # created_at inherited from BaseModel
