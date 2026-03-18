from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidRole, NotFound
from app.core.roles import OrgRole, SystemRole
from app.models.organization import Organization
from app.models.org_membership import OrgMembership
from app.models.user import User

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
        system_role=SystemRole.USER,
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


async def list_all_orgs(db: AsyncSession) -> list[dict]:
    """
    List all organizations with owner email and member count.
    System admin only — returns data across all orgs.
    """
    # Subquery: count members per org
    member_count_sq = (
        select(
            OrgMembership.org_id,
            func.count(OrgMembership.id).label("member_count"),
        )
        .group_by(OrgMembership.org_id)
        .subquery()
    )

    # Subquery: owner email per org
    owner_sq = (
        select(
            OrgMembership.org_id,
            User.email.label("owner_email"),
        )
        .join(User, OrgMembership.user_id == User.id)
        .where(OrgMembership.org_role == OrgRole.OWNER)
        .subquery()
    )

    stmt = (
        select(
            Organization.id,
            Organization.name,
            Organization.created_at,
            owner_sq.c.owner_email,
            func.coalesce(member_count_sq.c.member_count, 0).label("member_count"),
        )
        .outerjoin(owner_sq, Organization.id == owner_sq.c.org_id)
        .outerjoin(member_count_sq, Organization.id == member_count_sq.c.org_id)
        .order_by(Organization.created_at.desc())
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "id": row.id,
            "name": row.name,
            "created_at": row.created_at,
            "owner_email": row.owner_email,
            "member_count": row.member_count,
        }
        for row in rows
    ]


# ── Org management (System Admin) ──


async def get_org_by_id(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> Optional[Organization]:
    """Fetch an organization by ID."""
    stmt = select(Organization).where(Organization.id == org_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def rename_org(
    db: AsyncSession,
    org: Organization,
    new_name: str,
) -> Organization:
    """Rename an organization."""
    org.name = new_name
    await db.flush()
    return org


async def delete_org(
    db: AsyncSession,
    org: Organization,
) -> None:
    """Delete an organization and all its memberships."""
    await db.execute(
        delete(OrgMembership).where(OrgMembership.org_id == org.id)
    )
    await db.delete(org)
    await db.flush()


async def transfer_ownership(
    db: AsyncSession,
    org_id: uuid.UUID,
    new_owner_email: str,
) -> OrgMembership:
    """
    Transfer org ownership to another user.

    The new owner must already be a member of the org.
    The current owner is demoted to admin.
    """
    # Find new owner's user record
    new_owner = await find_user_by_email(db, new_owner_email)
    if not new_owner:
        raise NotFound(f"User with email {new_owner_email} not found")

    # Find their membership in this org
    new_owner_membership = await find_existing_membership(db, org_id, new_owner.id)
    if not new_owner_membership:
        raise NotFound(
            f"User {new_owner_email} is not a member of this organization"
        )

    # Find current owner
    stmt = (
        select(OrgMembership)
        .where(OrgMembership.org_id == org_id)
        .where(OrgMembership.org_role == OrgRole.OWNER)
    )
    result = await db.execute(stmt)
    current_owner_membership = result.scalar_one_or_none()

    if current_owner_membership:
        if current_owner_membership.id == new_owner_membership.id:
            raise InvalidRole("This user is already the owner")
        # Demote current owner to admin
        current_owner_membership.org_role = OrgRole.ADMIN

    # Promote new owner
    new_owner_membership.org_role = OrgRole.OWNER
    await db.flush()
    return new_owner_membership
