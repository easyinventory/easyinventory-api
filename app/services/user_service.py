from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.services.org_service import create_default_org


async def get_or_create_user(
    db: AsyncSession,
    cognito_sub: str,
    email: str,
) -> User:
    """
    Look up a user by cognito_sub. If not found, create one.

    If the user is the bootstrap admin, also creates the default
    organization and adds them as ORG_OWNER.
    """
    stmt = select(User).where(User.cognito_sub == cognito_sub)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is not None:
        return user

    # Determine role
    is_admin = _is_bootstrap_admin(email)
    role = "SYSTEM_ADMIN" if is_admin else "SYSTEM_USER"

    user = User(
        cognito_sub=cognito_sub,
        email=email,
        system_role=role,
    )
    db.add(user)
    await db.flush()

    # Bootstrap admin gets a default org
    if is_admin:
        await create_default_org(db=db, owner_id=user.id)

    return user


def _is_bootstrap_admin(email: str) -> bool:
    bootstrap_email = settings.BOOTSTRAP_ADMIN_EMAIL
    if not bootstrap_email:
        return False
    return email.strip().lower() == bootstrap_email.strip().lower()
