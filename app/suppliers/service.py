from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.supplier import Supplier


async def list_suppliers(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> list[Supplier]:
    """List all suppliers for an org, ordered by name."""
    stmt = select(Supplier).where(Supplier.org_id == org_id).order_by(Supplier.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_supplier(
    db: AsyncSession,
    supplier_id: uuid.UUID,
    org_id: uuid.UUID,
) -> Optional[Supplier]:
    """Get a single supplier by ID within an org."""
    stmt = (
        select(Supplier)
        .where(Supplier.id == supplier_id)
        .where(Supplier.org_id == org_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_supplier(
    db: AsyncSession,
    org_id: uuid.UUID,
    name: str,
    contact_name: Optional[str] = None,
    contact_email: Optional[str] = None,
    contact_phone: Optional[str] = None,
    notes: Optional[str] = None,
) -> Supplier:
    """Create a new supplier."""
    supplier = Supplier(
        org_id=org_id,
        name=name,
        contact_name=contact_name,
        contact_email=contact_email,
        contact_phone=contact_phone,
        notes=notes,
    )
    db.add(supplier)
    await db.flush()
    return supplier


async def update_supplier(
    db: AsyncSession,
    supplier: Supplier,
    **fields: object,
) -> Supplier:
    """Update a supplier's fields. Only non-None values are applied."""
    for key, value in fields.items():
        if value is not None:
            setattr(supplier, key, value)
    await db.flush()
    return supplier


async def delete_supplier(
    db: AsyncSession,
    supplier: Supplier,
) -> None:
    """Permanently delete a supplier."""
    await db.delete(supplier)
    await db.flush()
