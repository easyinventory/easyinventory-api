"""Routes for Fixture CRUD operations."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.roles import OrgRole
from app.layouts.deps import get_layout_from_path
from app.models.fixture import Fixture
from app.models.layout_version import LayoutVersion
from app.orgs.deps import RequireOrgRole
from app.fixtures.schemas import FixtureCreate, FixtureRead, FixtureUpdate
from app.fixtures import service

router = APIRouter(
    prefix="/api/stores/{store_id}/layouts/{layout_version_id}/fixtures",
    tags=["fixtures"],
)

# ── Read endpoints (all org members) ──────────────────────────────────────────


@router.get("", response_model=list[FixtureRead])
async def list_fixtures(
    db: AsyncSession = Depends(get_db),
    layout: LayoutVersion = Depends(get_layout_from_path),
) -> list[Fixture]:
    """Return all fixtures for the layout version ordered by creation date."""
    return await service.list_fixtures(db, layout.id)


@router.get("/{fixture_id}", response_model=FixtureRead)
async def get_fixture(
    fixture_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    layout: LayoutVersion = Depends(get_layout_from_path),
) -> Fixture:
    """Return a single fixture by ID."""
    return await service.get_fixture(db, fixture_id, layout.id)


# ── Write endpoints (OWNER or ADMIN only) ─────────────────────────────────────


@router.post("", response_model=FixtureRead, status_code=status.HTTP_201_CREATED)
async def create_fixture(
    data: FixtureCreate,
    db: AsyncSession = Depends(get_db),
    layout: LayoutVersion = Depends(get_layout_from_path),
    _: object = Depends(RequireOrgRole(OrgRole.OWNER, OrgRole.ADMIN)),
) -> Fixture:
    """
    Create a new fixture within a layout version.

    All cells must lie within the layout grid and must not overlap existing zones
    or fixtures.
    """
    return await service.create_fixture(db, layout.id, data)


@router.put("/{fixture_id}", response_model=FixtureRead)
async def update_fixture(
    fixture_id: uuid.UUID,
    data: FixtureUpdate,
    db: AsyncSession = Depends(get_db),
    layout: LayoutVersion = Depends(get_layout_from_path),
    _: object = Depends(RequireOrgRole(OrgRole.OWNER, OrgRole.ADMIN)),
) -> Fixture:
    """Partially update a fixture's type, name, and/or cells."""
    return await service.update_fixture(db, fixture_id, layout.id, data)


@router.delete("/{fixture_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fixture(
    fixture_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    layout: LayoutVersion = Depends(get_layout_from_path),
    _: object = Depends(RequireOrgRole(OrgRole.OWNER, OrgRole.ADMIN)),
) -> None:
    """Delete a fixture by ID."""
    await service.delete_fixture(db, fixture_id, layout.id)
