"""Routes for Zone CRUD operations."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.roles import OrgRole
from app.layouts.deps import get_layout_from_path
from app.models.layout_version import LayoutVersion
from app.models.zone import Zone
from app.orgs.deps import RequireOrgRole
from app.zones.schemas import ZoneCreate, ZoneRead, ZoneUpdate
from app.zones import service

router = APIRouter(
    prefix="/api/stores/{store_id}/layouts/{layout_version_id}/zones",
    tags=["zones"],
)

# ── Read endpoints (all org members) ──────────────────────────────────────────


@router.get("", response_model=list[ZoneRead])
async def list_zones(
    db: AsyncSession = Depends(get_db),
    layout: LayoutVersion = Depends(get_layout_from_path),
) -> list[Zone]:
    """Return all zones for the layout version ordered by creation date."""
    zones = await service.list_zones(db, layout.id)
    return zones


@router.get("/{zone_id}", response_model=ZoneRead)
async def get_zone(
    zone_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    layout: LayoutVersion = Depends(get_layout_from_path),
) -> Zone:
    """Return a single zone by ID."""
    zone = await service.get_zone(db, zone_id, layout.id)
    return zone


# ── Write endpoints (OWNER or ADMIN only) ─────────────────────────────────────


@router.post("", response_model=ZoneRead, status_code=status.HTTP_201_CREATED)
async def create_zone(
    data: ZoneCreate,
    db: AsyncSession = Depends(get_db),
    layout: LayoutVersion = Depends(get_layout_from_path),
    _: object = Depends(RequireOrgRole(OrgRole.OWNER, OrgRole.ADMIN)),
) -> Zone:
    """
    Create a new zone within a layout version.

    All cells must lie within the layout grid and must not overlap existing zones.
    """
    zone = await service.create_zone(db, layout.id, data)
    return zone


@router.put("/{zone_id}", response_model=ZoneRead)
async def update_zone(
    zone_id: uuid.UUID,
    data: ZoneUpdate,
    db: AsyncSession = Depends(get_db),
    layout: LayoutVersion = Depends(get_layout_from_path),
    _: object = Depends(RequireOrgRole(OrgRole.OWNER, OrgRole.ADMIN)),
) -> Zone:
    """Partially update a zone's name, color, and/or cells."""
    zone = await service.update_zone(db, zone_id, layout.id, data)
    return zone


@router.delete("/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_zone(
    zone_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    layout: LayoutVersion = Depends(get_layout_from_path),
    _: object = Depends(RequireOrgRole(OrgRole.OWNER, OrgRole.ADMIN)),
) -> None:
    """Delete a zone by ID."""
    await service.delete_zone(db, zone_id, layout.id)
