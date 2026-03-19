"""
Org membership service — member CRUD operations within an organization.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.org_membership import OrgMembership
from app.models.user import User


async def list_org_members(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> list[dict]:
    """List all members of an org with their user email."""
    stmt = (
        select(OrgMembership, User.email)
        .join(User, OrgMembership.user_id == User.id)
        .where(OrgMembership.org_id == org_id)
        .order_by(OrgMembership.joined_at)
    )
    result = await db.execute(stmt)
    return [
        {
            "id": m.id,
            "user_id": m.user_id,
            "email": email,
            "org_role": m.org_role,
            "is_active": m.is_active,
            "joined_at": m.joined_at,
        }
        for m, email in result.all()
    ]


async def get_membership_by_id(
    db: AsyncSession,
    membership_id: uuid.UUID,
    org_id: uuid.UUID,
) -> Optional[OrgMembership]:
    """Fetch a single membership by ID within an org."""
    stmt = (
        select(OrgMembership)
        .where(OrgMembership.id == membership_id)
        .where(OrgMembership.org_id == org_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def find_existing_membership(
    db: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Optional[OrgMembership]:
    """Check if a user already has a membership in this org (active or not)."""
    stmt = (
        select(OrgMembership)
        .where(OrgMembership.org_id == org_id)
        .where(OrgMembership.user_id == user_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_membership(
    db: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    org_role: str,
    is_active: bool = True,
) -> OrgMembership:
    """Create a new org membership."""
    membership = OrgMembership(
        org_id=org_id,
        user_id=user_id,
        org_role=org_role,
        is_active=is_active,
    )
    db.add(membership)
    await db.flush()
    return membership


async def update_role(
    db: AsyncSession,
    membership: OrgMembership,
    new_role: str,
) -> OrgMembership:
    """Update a membership's role."""
    membership.org_role = new_role
    await db.flush()
    return membership


async def set_active_status(
    db: AsyncSession,
    membership: OrgMembership,
    is_active: bool,
) -> OrgMembership:
    """Set a membership's active status."""
    membership.is_active = is_active
    await db.flush()
    return membership


async def delete_membership(
    db: AsyncSession,
    membership: OrgMembership,
) -> None:
    """Permanently delete a membership."""
    await db.delete(membership)
    await db.flush()
