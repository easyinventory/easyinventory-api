"""
System admin service — org management and user management operations.

These functions are only accessible to SYSTEM_ADMIN users.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidRole, NotFound
from app.core.roles import OrgRole
from app.models.organization import Organization
from app.models.org_membership import OrgMembership
from app.models.user import User

# ── Data containers ──


@dataclass
class UserWithOrgCount:
    id: uuid.UUID
    email: str
    system_role: str
    is_active: bool
    created_at: datetime
    org_count: int


@dataclass
class OrgWithDetails:
    id: uuid.UUID
    name: str
    created_at: datetime
    owner_email: str | None
    member_count: int


async def list_all_orgs(db: AsyncSession) -> list[Organization]:
    """
    List all organizations with memberships and users loaded.
    System admin only — returns data across all orgs.
    """
    stmt = select(Organization).order_by(Organization.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


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
    await db.execute(delete(OrgMembership).where(OrgMembership.org_id == org.id))
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
    from app.users.service import find_user_by_email
    from app.orgs.service import find_existing_membership

    # Find new owner's user record
    new_owner = await find_user_by_email(db, new_owner_email)
    if not new_owner:
        raise NotFound(f"User with email {new_owner_email} not found")

    # Find their membership in this org
    new_owner_membership = await find_existing_membership(db, org_id, new_owner.id)
    if not new_owner_membership:
        raise NotFound(f"User {new_owner_email} is not a member of this organization")

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


async def list_all_users(db: AsyncSession) -> list[User]:
    """List all users with memberships loaded."""
    stmt = select(User).order_by(User.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ── Aggregate queries ──


async def list_users_with_org_counts(
    db: AsyncSession,
) -> list[UserWithOrgCount]:
    """
    List all users with their active-organization counts.

    Performs a single aggregate query for org counts instead of
    materializing full membership collections for every user.
    """
    users = await list_all_users(db)

    user_ids = [user.id for user in users]
    org_counts: dict[uuid.UUID, int] = {}
    if user_ids:
        stmt = (
            select(OrgMembership.user_id, func.count(OrgMembership.id))
            .where(
                OrgMembership.user_id.in_(user_ids),
                OrgMembership.is_active.is_(True),
            )
            .group_by(OrgMembership.user_id)
        )
        result = await db.execute(stmt)
        org_counts = {user_id: count for user_id, count in result.all()}

    return [
        UserWithOrgCount(
            id=user.id,
            email=user.email,
            system_role=user.system_role,
            is_active=user.is_active,
            created_at=user.created_at,
            org_count=org_counts.get(user.id, 0),
        )
        for user in users
    ]


async def list_orgs_with_details(db: AsyncSession) -> list[OrgWithDetails]:
    """
    List all organizations with owner email and member count.

    Uses SQL aggregates and a subquery to compute owner_email and
    member_count without materializing full related collections.
    """
    owner_subq = (
        select(
            OrgMembership.org_id,
            User.email.label("owner_email"),
        )
        .join(User, User.id == OrgMembership.user_id)
        .where(OrgMembership.org_role == OrgRole.OWNER)
        .subquery()
    )

    stmt = (
        select(
            Organization.id,
            Organization.name,
            Organization.created_at,
            func.count(OrgMembership.id).label("member_count"),
            owner_subq.c.owner_email,
        )
        .select_from(Organization)
        .join(OrgMembership, OrgMembership.org_id == Organization.id, isouter=True)
        .join(owner_subq, owner_subq.c.org_id == Organization.id, isouter=True)
        .group_by(
            Organization.id,
            Organization.name,
            Organization.created_at,
            owner_subq.c.owner_email,
        )
    )

    result = await db.execute(stmt)
    return [
        OrgWithDetails(
            id=row.id,
            name=row.name,
            created_at=row.created_at,
            owner_email=row.owner_email,
            member_count=row.member_count,
        )
        for row in result.all()
    ]


async def get_org_owner_and_member_count(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> tuple[str | None, int]:
    """
    Return ``(owner_email, member_count)`` for a single organization.

    Used after mutations (e.g. rename) to build the response without
    loading full related collections.
    """
    owner_subq = (
        select(
            OrgMembership.org_id,
            User.email.label("owner_email"),
        )
        .join(User, User.id == OrgMembership.user_id)
        .where(
            OrgMembership.org_role == OrgRole.OWNER,
            OrgMembership.org_id == org_id,
        )
        .subquery()
    )

    stmt = (
        select(
            func.count(OrgMembership.id).label("member_count"),
            owner_subq.c.owner_email,
        )
        .select_from(Organization)
        .join(OrgMembership, OrgMembership.org_id == Organization.id, isouter=True)
        .join(owner_subq, owner_subq.c.org_id == Organization.id, isouter=True)
        .where(Organization.id == org_id)
        .group_by(owner_subq.c.owner_email)
    )

    result = await db.execute(stmt)
    row = result.one_or_none()

    owner_email = row.owner_email if row is not None else None
    member_count = row.member_count if row is not None else 0
    return owner_email, member_count
