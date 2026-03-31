from __future__ import annotations

import uuid

from fastapi import Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.org_membership import OrgMembership
from app.models.store import Store
from app.orgs.deps import get_current_org_membership
from app.stores.service import get_by_id as get_store_by_id


async def get_store_from_path(
    store_id: uuid.UUID = Path(..., description="Store ID"),
    db: AsyncSession = Depends(get_db),
    membership: OrgMembership = Depends(get_current_org_membership),
) -> Store:
    """
    Extract ``store_id`` from the path and validate org ownership.

    Raises 404 if the store does not exist or belongs to a different org.
    """
    return await get_store_by_id(db, store_id, membership.org_id)
