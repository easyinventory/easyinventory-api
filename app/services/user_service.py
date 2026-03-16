from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.models.org_membership import OrgMembership
from app.services.org_service import create_default_org


async def get_or_create_user(
    db: AsyncSession,
    cognito_sub: str,
    email: str,
) -> User:
    """
    Look up a user by cognito_sub. If not found, check for a
    placeholder user (invited but hasn't signed up yet). If no
    placeholder, create a new user.
    """
    # 1. Check by cognito_sub (normal login)
    stmt = select(User).where(User.cognito_sub == cognito_sub)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is not None:
        return user

    # 2. Check for placeholder user (invited before signup)
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
    is_admin = _is_bootstrap_admin(email)
    role = "SYSTEM_ADMIN" if is_admin else "SYSTEM_USER"

    user = User(
        cognito_sub=cognito_sub,
        email=email,
        system_role=role,
    )
    db.add(user)
    await db.flush()

    if is_admin:
        await create_default_org(db=db, owner_id=user.id)

    return user


def _is_bootstrap_admin(email: str) -> bool:
    bootstrap_email = settings.BOOTSTRAP_ADMIN_EMAIL
    if not bootstrap_email:
        return False
    return email.strip().lower() == bootstrap_email.strip().lower()
