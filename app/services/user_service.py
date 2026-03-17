from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import SystemRole
from app.models.user import User
from app.models.org_membership import OrgMembership


async def delete_user_completely(
    db: AsyncSession,
    user: User,
) -> None:
    """Delete a user and all their org memberships from the local DB."""
    await db.execute(delete(OrgMembership).where(OrgMembership.user_id == user.id))
    await db.delete(user)
    await db.flush()


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
