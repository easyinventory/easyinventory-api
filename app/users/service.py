"""
User service — user lookup and lifecycle operations.

Merges former user_service.py functions with user-centric functions
previously housed in org_service.py.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import SystemRole
from app.models.org_membership import OrgMembership
from app.models.user import User


async def get_user_by_id(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> Optional[User]:
    """Fetch a user by ID."""
    stmt = select(User).where(User.id == user_id)
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


async def get_or_create_user(
    db: AsyncSession,
    cognito_sub: str,
    email: str,
) -> User:
    """
    Look up a user by cognito_sub. If not found, check for a
    placeholder user (invited or bootstrap). If no placeholder,
    create a new SYSTEM_USER.

    Bootstrap admin promotion is handled at startup by
    ``app.core.bootstrap.run_bootstrap`` — this function no longer
    needs to check BOOTSTRAP_ADMIN_EMAIL.
    """
    # 1. Check by cognito_sub (normal login)
    stmt = select(User).where(User.cognito_sub == cognito_sub)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is not None:
        return user

    # 2. Check for placeholder user (invited or bootstrap, hasn't signed in yet)
    placeholder_stmt = select(User).where(
        User.email == email,
        User.cognito_sub.like("pending:%"),
    )
    placeholder_result = await db.execute(placeholder_stmt)
    placeholder = placeholder_result.scalar_one_or_none()

    if placeholder is not None:
        # Claim the placeholder — set real cognito_sub, activate
        placeholder.cognito_sub = cognito_sub
        placeholder.is_active = True

        # Activate all their org memberships
        membership_stmt = (
            select(OrgMembership)
            .where(OrgMembership.user_id == placeholder.id)
            .where(OrgMembership.is_active == False)  # noqa: E712
        )
        membership_result = await db.execute(membership_stmt)
        memberships = membership_result.scalars().all()
        for m in memberships:
            m.is_active = True

        await db.flush()
        return placeholder

    # 3. Brand new user — no placeholder exists
    user = User(
        cognito_sub=cognito_sub,
        email=email,
        system_role=SystemRole.USER,
    )
    db.add(user)
    await db.flush()

    return user


async def delete_user_completely(
    db: AsyncSession,
    user: User,
) -> None:
    """Delete a user and all their org memberships from the local DB."""
    await db.execute(delete(OrgMembership).where(OrgMembership.user_id == user.id))
    await db.delete(user)
    await db.flush()
