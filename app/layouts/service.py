"""Service layer for LayoutVersion CRUD operations."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models.layout_version import LayoutVersion


async def create_layout_version(
    db: AsyncSession,
    store_id: uuid.UUID,
    rows: int,
    cols: int,
) -> LayoutVersion:
    """Create a new layout version with an auto-incremented version_number."""
    # Compute next version_number as MAX(version_number) + 1, starting at 1
    subq = select(func.coalesce(func.max(LayoutVersion.version_number), 0) + 1).where(
        LayoutVersion.store_id == store_id
    )
    result = await db.execute(subq)
    next_version = result.scalar_one()

    layout = LayoutVersion(
        store_id=store_id,
        version_number=next_version,
        rows=rows,
        cols=cols,
        is_active=False,
    )
    db.add(layout)
    await db.flush()
    await db.refresh(layout)
    return layout


async def activate_layout_version(
    db: AsyncSession,
    layout_id: uuid.UUID,
    store_id: uuid.UUID,
) -> LayoutVersion:
    """Deactivate all versions for the store, then activate the specified one."""
    # Verify the target version exists and belongs to the store
    stmt = select(LayoutVersion).where(
        LayoutVersion.id == layout_id,
        LayoutVersion.store_id == store_id,
    )
    result = await db.execute(stmt)
    layout = result.scalar_one_or_none()
    if layout is None:
        raise NotFound(f"Layout version {layout_id} not found for store {store_id}")

    # Deactivate all versions for this store
    await db.execute(
        update(LayoutVersion)
        .where(LayoutVersion.store_id == store_id)
        .values(is_active=False)
    )

    # Activate the target version
    await db.execute(
        update(LayoutVersion)
        .where(LayoutVersion.id == layout_id)
        .values(is_active=True)
    )

    await db.flush()
    await db.refresh(layout)
    return layout


async def get_active_layout(
    db: AsyncSession,
    store_id: uuid.UUID,
) -> LayoutVersion:
    """Return the currently active layout version for the store."""
    # TODO(BE-07): add .options(selectinload(LayoutVersion.zones)) once the Zone
    #              model and relationship are introduced in the zones-cellset PR.
    stmt = select(LayoutVersion).where(
        LayoutVersion.store_id == store_id,
        LayoutVersion.is_active == True,  # noqa: E712
    )
    result = await db.execute(stmt)
    layout = result.scalar_one_or_none()
    if layout is None:
        raise NotFound(f"No active layout version found for store {store_id}")
    return layout


async def list_layout_versions(
    db: AsyncSession,
    store_id: uuid.UUID,
) -> list[LayoutVersion]:
    """Return all layout versions for the store ordered by version_number."""
    stmt = (
        select(LayoutVersion)
        .where(LayoutVersion.store_id == store_id)
        .order_by(LayoutVersion.version_number.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
