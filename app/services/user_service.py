from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User


async def get_or_create_user(
    db: AsyncSession,
    cognito_sub: str,
    email: str,
) -> User:
    """
    Look up a user by cognito_sub. If not found, create one.

    If the user's email matches BOOTSTRAP_ADMIN_EMAIL, they are
    created with SYSTEM_ADMIN role instead of the default SYSTEM_USER.
    """
    stmt = select(User).where(User.cognito_sub == cognito_sub)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is not None:
        return user

    # Determine role — bootstrap admin or regular user
    role = "SYSTEM_ADMIN" if _is_bootstrap_admin(email) else "SYSTEM_USER"

    user = User(
        cognito_sub=cognito_sub,
        email=email,
        system_role=role,
    )
    db.add(user)
    await db.flush()

    return user


def _is_bootstrap_admin(email: str) -> bool:
    """
    Check if this email should be auto-promoted to admin.

    Returns False if BOOTSTRAP_ADMIN_EMAIL is not set.
    Comparison is case-insensitive.
    """
    bootstrap_email = settings.BOOTSTRAP_ADMIN_EMAIL
    if not bootstrap_email:
        return False
    return email.strip().lower() == bootstrap_email.strip().lower()
