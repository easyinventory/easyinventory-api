from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.org_membership import OrgMembership
from app.schemas.org import OrgMembershipResponse

router = APIRouter(prefix="/api/orgs", tags=["organizations"])


@router.get("/me", response_model=list[OrgMembershipResponse])
async def get_my_orgs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[OrgMembership]:
    """
    Return the current user's organization memberships.

    Includes the organization details nested in each membership.
    Returns an empty list if the user has no memberships.
    """
    stmt = (
        select(OrgMembership)
        .where(OrgMembership.user_id == current_user.id)
        .where(OrgMembership.is_active == True)
        .options(selectinload(OrgMembership.organization))
    )
    result = await db.execute(stmt)
    memberships = result.scalars().all()

    return list(memberships)
