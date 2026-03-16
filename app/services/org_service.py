from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.org_membership import OrgMembership
from app.models.user import User


async def create_default_org(
    db: AsyncSession,
    owner_id: uuid.UUID,
) -> Organization:
    """
    Create the default organization and add the user as ORG_OWNER.

    Called once during bootstrap admin's first login. If the admin
    already has an org membership, this is a no-op.

    Args:
        db: Active database session
        owner_id: The bootstrap admin's user ID

    Returns:
        The created or existing Organization
    """
    # Check if this user already has any org membership
    stmt = select(OrgMembership).where(OrgMembership.user_id == owner_id)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing is not None:
        # Already has an org — fetch and return it
        org_stmt = select(Organization).where(Organization.id == existing.org_id)
        org_result = await db.execute(org_stmt)
        org: Organization | None = org_result.scalar_one_or_none()
        if org is not None:
            return org

    # Create the org
    org = Organization(name="Default Organization")
    db.add(org)
    await db.flush()

    # Add the admin as owner
    membership = OrgMembership(
        org_id=org.id,
        user_id=owner_id,
        org_role="ORG_OWNER",
    )
    db.add(membership)
    await db.flush()

    return org


# ── New: member management ──


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


async def find_user_by_email(
    db: AsyncSession,
    email: str,
) -> Optional[User]:
    """Find a user by email. Returns None if not found."""
    stmt = select(User).where(User.email == email)
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


async def create_placeholder_user(
    db: AsyncSession,
    email: str,
) -> User:
    """Create a placeholder for an invited email that hasn't signed up."""
    user = User(
        cognito_sub=f"pending:{email}",
        email=email,
        system_role="SYSTEM_USER",
        is_active=False,
    )
    db.add(user)
    await db.flush()
    return user


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


async def get_user_by_id(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> Optional[User]:
    """Fetch a user by ID."""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
