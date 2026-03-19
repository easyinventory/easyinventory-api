from __future__ import annotations

import uuid

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.core.database import get_db
from app.models.org_membership import OrgMembership
from app.models.user import User


async def get_current_org_membership(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_org_id: str | None = Header(None),
) -> OrgMembership:
    """
    Get the current user's active org membership.

    If the ``X-Org-Id`` header is supplied the membership for that
    specific org is returned.  Otherwise falls back to the most
    recent active membership.

    Raises 403 if user has no active org membership (or the requested
    org is not accessible to them).
    """
    if x_org_id is not None:
        try:
            org_uuid = uuid.UUID(x_org_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid X-Org-Id header — must be a valid UUID",
            )

        stmt = (
            select(OrgMembership)
            .where(OrgMembership.user_id == current_user.id)
            .where(OrgMembership.org_id == org_uuid)
            .where(OrgMembership.is_active == True)  # noqa: E712
        )
        result = await db.execute(stmt)
        membership = result.scalars().first()

        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No active membership in the requested organization",
            )
        return membership

    # Fallback: most-recent active membership
    stmt = (
        select(OrgMembership)
        .where(OrgMembership.user_id == current_user.id)
        .where(OrgMembership.is_active == True)  # noqa: E712
        .order_by(OrgMembership.joined_at.desc(), OrgMembership.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    membership = result.scalars().first()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active organization membership",
        )

    return membership


class RequireOrgRole:
    """
    Callable dependency that checks the user's org_role.

    Usage::

        from app.core.roles import OrgRole

        @router.post("/invite")
        async def invite(
            membership = Depends(RequireOrgRole(OrgRole.OWNER, OrgRole.ADMIN)),
        ):
            ...
    """

    def __init__(self, *allowed_roles: str):
        self.allowed_roles = allowed_roles

    async def __call__(
        self,
        membership: OrgMembership = Depends(get_current_org_membership),
    ) -> OrgMembership:
        if membership.org_role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient org permissions",
            )
        return membership
