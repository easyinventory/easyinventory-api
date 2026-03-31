"""Routes for LayoutVersion CRUD operations."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.roles import OrgRole
from app.models.store import Store
from app.orgs.deps import RequireOrgRole
from app.stores.deps import get_store_from_path
from app.layouts.schemas import LayoutVersionCreate, LayoutVersionRead
from app.models.layout_version import LayoutVersion
from app.layouts import service

router = APIRouter(prefix="/api/stores/{store_id}/layouts", tags=["layouts"])

# ── Read endpoints (all org members) ──────────────────────────────────────────


@router.get("", response_model=list[LayoutVersionRead])
async def list_layout_versions(
    db: AsyncSession = Depends(get_db),
    store: Store = Depends(get_store_from_path),
) -> list[LayoutVersion]:
    """Return all layout versions for the store ordered by version_number."""
    versions = await service.list_layout_versions(db, store.id)
    return versions


# NOTE: /active must be declared before /{layout_id} to avoid routing conflict.
@router.get("/active", response_model=LayoutVersionRead)
async def get_active_layout(
    db: AsyncSession = Depends(get_db),
    store: Store = Depends(get_store_from_path),
) -> LayoutVersion:
    """Return the currently active layout version with zones eagerly loaded."""
    layout = await service.get_active_layout(db, store.id)
    return layout


# ── Write endpoints (OWNER or ADMIN only) ─────────────────────────────────────


@router.post("", response_model=LayoutVersionRead, status_code=status.HTTP_201_CREATED)
async def create_layout_version(
    data: LayoutVersionCreate,
    db: AsyncSession = Depends(get_db),
    store: Store = Depends(get_store_from_path),
    _: object = Depends(RequireOrgRole(OrgRole.OWNER, OrgRole.ADMIN)),
) -> LayoutVersion:
    """Create a new layout version with an auto-incremented version_number."""
    layout = await service.create_layout_version(db, store.id, data.rows, data.cols)
    return layout


@router.post("/{layout_id}/activate", response_model=LayoutVersionRead)
async def activate_layout_version(
    layout_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    store: Store = Depends(get_store_from_path),
    _: object = Depends(RequireOrgRole(OrgRole.OWNER, OrgRole.ADMIN)),
) -> LayoutVersion:
    """Activate a layout version, deactivating all others for the store."""
    layout = await service.activate_layout_version(db, layout_id, store.id)
    return layout
