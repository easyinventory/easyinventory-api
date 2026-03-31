"""Service layer for Fixture CRUD operations."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFound
from app.models.fixture import Fixture, FixtureType
from app.models.layout_version import LayoutVersion
from app.models.zone import Zone
from app.fixtures.schemas import FixtureCreate, FixtureUpdate

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


async def _check_overlap(
    db: AsyncSession,
    layout_version_id: uuid.UUID,
    cells: list[dict],
    exclude_fixture_id: Optional[uuid.UUID] = None,
) -> None:
    """
    Raise AppError(409) if the given cells overlap with any existing fixture
    or zone in the layout.
    """
    requested: set[tuple[int, int]] = {(c["row"], c["col"]) for c in cells}

    # Check against existing fixtures
    fixture_result = await db.execute(
        select(Fixture).where(Fixture.layout_version_id == layout_version_id)
    )
    for fixture in fixture_result.scalars().all():
        if exclude_fixture_id and fixture.id == exclude_fixture_id:
            continue
        fixture_cells: set[tuple[int, int]] = {
            (c["row"], c["col"]) for c in fixture.cells
        }
        overlap = requested & fixture_cells
        if overlap:
            label = (
                f"fixture '{fixture.name}'"
                if fixture.name
                else f"a {fixture.fixture_type.value} fixture"
            )
            raise AppError(
                f"Cells {sorted(overlap)} overlap with existing {label}",
                status_code=409,
            )

    # Check against existing zones
    zone_result = await db.execute(
        select(Zone).where(Zone.layout_version_id == layout_version_id)
    )
    for zone in zone_result.scalars().all():
        zone_cells: set[tuple[int, int]] = {(c["row"], c["col"]) for c in zone.cells}
        overlap = requested & zone_cells
        if overlap:
            raise AppError(
                f"Cells {sorted(overlap)} overlap with existing zone '{zone.name}'",
                status_code=409,
            )


# ── Public service functions ──────────────────────────────────────────────────


async def create_fixture(
    db: AsyncSession,
    layout_version_id: uuid.UUID,
    data: FixtureCreate,
) -> Fixture:
    """
    Create a new fixture within a layout version.

    Validates:
    - All cells are within grid bounds (400 if not)
    - No cells overlap with existing fixtures or zones (409 if they do)
    - At least 1 cell / no duplicates (validated by schema)
    """
    layout = await _get_layout(db, layout_version_id)
    cells = [{"row": c.row, "col": c.col} for c in data.cells]

    _check_bounds(layout, cells)
    await _check_overlap(db, layout_version_id, cells)

    fixture = Fixture(
        layout_version_id=layout_version_id,
        fixture_type=data.fixture_type,
        name=data.name,
        cells=cells,
    )
    db.add(fixture)
    await db.flush()
    await db.refresh(fixture)
    return fixture


async def get_fixture(
    db: AsyncSession,
    fixture_id: uuid.UUID,
    layout_version_id: uuid.UUID,
) -> Fixture:
    """Return a fixture by ID, scoped to layout_version_id; raises NotFound if missing."""
    result = await db.execute(
        select(Fixture).where(
            Fixture.id == fixture_id,
            Fixture.layout_version_id == layout_version_id,
        )
    )
    fixture = result.scalar_one_or_none()
    if fixture is None:
        raise NotFound(
            f"Fixture {fixture_id} not found in layout version {layout_version_id}"
        )
    return fixture


async def list_fixtures(
    db: AsyncSession,
    layout_version_id: uuid.UUID,
) -> list[Fixture]:
    """Return all fixtures for a layout version ordered by creation date."""
    result = await db.execute(
        select(Fixture)
        .where(Fixture.layout_version_id == layout_version_id)
        .order_by(Fixture.created_at)
    )
    return list(result.scalars().all())


async def update_fixture(
    db: AsyncSession,
    fixture_id: uuid.UUID,
    layout_version_id: uuid.UUID,
    data: FixtureUpdate,
) -> Fixture:
    """Partially update a fixture's type, name, and/or cells."""
    fixture = await get_fixture(db, fixture_id, layout_version_id)

    if data.cells is not None:
        layout = await _get_layout(db, layout_version_id)
        cells = [{"row": c.row, "col": c.col} for c in data.cells]
        _check_bounds(layout, cells)
        await _check_overlap(
            db, layout_version_id, cells, exclude_fixture_id=fixture_id
        )
        fixture.cells = cells

    if data.fixture_type is not None:
        fixture.fixture_type = data.fixture_type

    if data.name is not None:
        fixture.name = data.name

    await db.flush()
    await db.refresh(fixture)
    return fixture


async def delete_fixture(
    db: AsyncSession,
    fixture_id: uuid.UUID,
    layout_version_id: uuid.UUID,
) -> None:
    """Delete a fixture by ID."""
    fixture = await get_fixture(db, fixture_id, layout_version_id)
    await db.delete(fixture)
    await db.flush()
