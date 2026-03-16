from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.org_membership import OrgMembership


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
