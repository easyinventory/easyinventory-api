"""
System admin service — org management and user management operations.

These functions are only accessible to SYSTEM_ADMIN users.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload, with_expression

from app.core.exceptions import InvalidRole, NotFound
from app.core.roles import OrgRole
from app.models.organization import Organization
from app.models.org_membership import OrgMembership
from app.models.user import User


def _owner_email_subquery():
    """Correlated subquery that returns the owner's email for an org row."""
    return (
        select(User.email)
        .join(OrgMembership, OrgMembership.user_id == User.id)
        .where(OrgMembership.org_id == Organization.id)
        .where(OrgMembership.org_role == OrgRole.OWNER)
        .correlate(Organization)
        .scalar_subquery()
    )


def _member_count_subquery():
    """Correlated subquery that returns the total membership count for an org row."""
    return (
        select(func.count())
        .select_from(OrgMembership)
        .where(OrgMembership.org_id == Organization.id)
        .correlate(Organization)
        .scalar_subquery()
    )


async def list_all_orgs(db: AsyncSession) -> list[Organization]:
    """
    List all organizations with owner_email and member_count computed in SQL.
    System admin only — returns data across all orgs.
    """
    stmt = (
        select(Organization)
        .options(
            noload(Organization.memberships),
            with_expression(Organization.owner_email, _owner_email_subquery()),
            with_expression(Organization.member_count, _member_count_subquery()),
        )
        .order_by(Organization.created_at.desc())
    )
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


async def get_org_by_id_with_stats(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> Optional[Organization]:
    """Fetch an organization by ID with owner_email and member_count computed in SQL."""
    stmt = (
        select(Organization)
        .where(Organization.id == org_id)
        .options(
            noload(Organization.memberships),
            with_expression(Organization.owner_email, _owner_email_subquery()),
            with_expression(Organization.member_count, _member_count_subquery()),
        )
    )
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
