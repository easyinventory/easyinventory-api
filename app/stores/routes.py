from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.roles import OrgRole
from app.models.org_membership import OrgMembership
from app.orgs.deps import RequireOrgRole, get_current_org_membership
from app.stores.schemas import StoreCreate, StoreRead
from app.stores.service import create_store, list_stores

router = APIRouter(prefix="/api/stores", tags=["stores"])


@router.get("", response_model=list[StoreRead])
async def list_org_stores(
    db: AsyncSession = Depends(get_db),
    membership: OrgMembership = Depends(get_current_org_membership),
) -> list[StoreRead]:
    """List all stores for the current organization."""
    stores = await list_stores(db, membership.org_id)
    return [StoreRead.model_validate(s) for s in stores]


@router.post("", response_model=StoreRead, status_code=status.HTTP_201_CREATED)
async def create_new_store(
    data: StoreCreate,
    db: AsyncSession = Depends(get_db),
    membership: OrgMembership = Depends(RequireOrgRole(OrgRole.OWNER)),
) -> StoreRead:
    """Create a new store. Owner role required."""
    store = await create_store(db, membership.org_id, data.name)
    await db.commit()
    return StoreRead.model_validate(store)
