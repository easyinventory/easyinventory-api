from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_or_create_user(
    db: AsyncSession,
    cognito_sub: str,
    email: str,
) -> User:
    """
    Look up a user by cognito_sub. If not found, create one.

    This is called on every authenticated request via the
    get_current_user dependency. The lookup is indexed so it's fast.

    Args:
        db: Active database session
        cognito_sub: The 'sub' claim from the Cognito JWT
        email: The 'email' claim from the JWT

    Returns:
        The existing or newly created User instance
    """
    stmt = select(User).where(User.cognito_sub == cognito_sub)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is not None:
        return user

    # First login — create the user
    user = User(
        cognito_sub=cognito_sub,
        email=email,
        system_role="SYSTEM_USER",
    )
    db.add(user)
    await db.flush()

    return user
