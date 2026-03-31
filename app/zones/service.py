"""Service layer for Zone CRUD operations."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFound
from app.models.layout_version import LayoutVersion
from app.models.zone import Zone
from app.zones.schemas import ZoneCreate, ZoneUpdate

# ── Internal helpers ──────────────────────────────────────────────────────────


async def _get_layout(db: AsyncSession, layout_version_id: uuid.UUID) -> LayoutVersion:
    """Load a LayoutVersion by ID; raises NotFound if missing."""
    result = await db.execute(
        select(LayoutVersion).where(LayoutVersion.id == layout_version_id)
    )
    layout = result.scalar_one_or_none()
    if layout is None:
        raise NotFound(f"Layout version {layout_version_id} not found")
    return layout


def _check_bounds(layout: LayoutVersion, cells: list[dict]) -> None:
    """Raise AppError(400) if any cell falls outside the layout grid dimensions."""
    for cell in cells:
        row, col = cell["row"], cell["col"]
        if row < 0 or row >= layout.rows or col < 0 or col >= layout.cols:
            raise AppError(
                f"Cell ({row}, {col}) is outside the layout bounds "
                f"({layout.rows} rows × {layout.cols} cols)",
                status_code=400,
            )


async def _check_zone_overlap(
    db: AsyncSession,
    layout_version_id: uuid.UUID,
    cells: list[dict],
    exclude_zone_id: Optional[uuid.UUID] = None,
) -> None:
    """
    Raise AppError(status_code=409) if the given cells overlap with any existing zone
    in the layout (excluding the zone being updated, if provided).
    """
    stmt = select(Zone).where(Zone.layout_version_id == layout_version_id)
    result = await db.execute(stmt)
    existing_zones = result.scalars().all()

    requested: set[tuple[int, int]] = {(c["row"], c["col"]) for c in cells}
    for zone in existing_zones:
        if exclude_zone_id and zone.id == exclude_zone_id:
            continue
        zone_cells: set[tuple[int, int]] = {(c["row"], c["col"]) for c in zone.cells}
        overlap = requested & zone_cells
        if overlap:
            raise AppError(
                f"Cells {sorted(overlap)} overlap with existing zone '{zone.name}'",
                status_code=409,
            )

    # TODO(BE-08): also check overlap against fixtures once the Fixture model exists.


# ── Public service functions ──────────────────────────────────────────────────


async def create_zone(
    db: AsyncSession,
    layout_version_id: uuid.UUID,
    data: ZoneCreate,
) -> Zone:
    """
    Create a new zone within a layout version.

    Validates:
    - All cells are within grid bounds (400 if not)
    - No cells overlap with existing zones or fixtures (409 if they do)
    - At least 1 cell / no duplicates (validated by schema)
    """
    layout = await _get_layout(db, layout_version_id)
    cells = [{"row": c.row, "col": c.col} for c in data.cells]

    _check_bounds(layout, cells)
    await _check_zone_overlap(db, layout_version_id, cells)

    zone = Zone(
        layout_version_id=layout_version_id,
        name=data.name,
        color=data.color,
        cells=cells,
    )
    db.add(zone)
    await db.flush()
    await db.refresh(zone)
    return zone


async def get_zone(
    db: AsyncSession,
    zone_id: uuid.UUID,
    layout_version_id: uuid.UUID,
) -> Zone:
    """Return a zone by ID, scoped to layout_version_id; raises NotFound if missing."""
    result = await db.execute(
        select(Zone).where(
            Zone.id == zone_id,
            Zone.layout_version_id == layout_version_id,
        )
    )
    zone = result.scalar_one_or_none()
    if zone is None:
        raise NotFound(
            f"Zone {zone_id} not found in layout version {layout_version_id}"
        )
    return zone


async def list_zones(
    db: AsyncSession,
    layout_version_id: uuid.UUID,
) -> list[Zone]:
    """Return all zones for a layout version ordered by created_at."""
    result = await db.execute(
        select(Zone)
        .where(Zone.layout_version_id == layout_version_id)
        .order_by(Zone.created_at.asc(), Zone.id.asc())
    )
    return list(result.scalars().all())


async def update_zone(
    db: AsyncSession,
    zone_id: uuid.UUID,
    layout_version_id: uuid.UUID,
    data: ZoneUpdate,
) -> Zone:
    """
    Partially update a zone's name, color, and/or cells.

    If cells are updated, re-runs bounds and overlap validation (excluding
    the zone itself from the overlap check).
    """
    zone = await get_zone(db, zone_id, layout_version_id)

    if data.cells is not None:
        layout = await _get_layout(db, layout_version_id)
        cells = [{"row": c.row, "col": c.col} for c in data.cells]
        _check_bounds(layout, cells)
        await _check_zone_overlap(db, layout_version_id, cells, exclude_zone_id=zone_id)
        zone.cells = cells

    if data.name is not None:
        zone.name = data.name

    if data.color is not None:
        zone.color = data.color

    await db.flush()
    await db.refresh(zone)
    return zone


async def delete_zone(
    db: AsyncSession,
    zone_id: uuid.UUID,
    layout_version_id: uuid.UUID,
) -> None:
    """Delete a zone; cascade in the DB handles any child records."""
    zone = await get_zone(db, zone_id, layout_version_id)
    await db.delete(zone)
    await db.flush()
