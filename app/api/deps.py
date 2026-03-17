from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cognito import get_email_from_access_token, verify_token
from app.core.database import get_db
from app.models.org_membership import OrgMembership
from app.models.user import User
from app.services.user_service import get_or_create_user

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency: validate JWT → get or create user in DB.

    Usage:
        @router.get("/something")
        async def something(user: User = Depends(get_current_user)):
            print(user.id, user.email, user.system_role)

    Returns a User model instance (not raw claims).
    Raises 401 if token is missing, expired, or invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        claims: dict[str, Any] = verify_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Cognito access tokens don't include the email claim (only ID tokens do).
    # Fall back to a get_user API call so first-login user creation works.
    email = claims.get("email", "") or get_email_from_access_token(token)

    user = await get_or_create_user(
        db=db,
        cognito_sub=claims["sub"],
        email=email,
    )

    return user


def require_role(*allowed_roles: str) -> Callable[..., Any]:
    """
    Dependency factory that checks the user's system_role.

    Usage:
        from app.core.roles import SystemRole

        @router.get("/admin-only")
        async def admin_only(
            user: User = Depends(require_role(SystemRole.ADMIN)),
        ):
            ...

    Returns the User if they have one of the allowed roles.
    Raises 403 if they don't.
    """

    async def _check_role(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.system_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return _check_role


async def get_current_org_membership(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrgMembership:
    """
    Get the current user's active org membership.
    Raises 403 if user has no active org membership.
    """
    from sqlalchemy import select

    stmt = (
        select(OrgMembership)
        .where(OrgMembership.user_id == current_user.id)
        .where(OrgMembership.is_active == True)  # noqa: E712
        .order_by(OrgMembership.joined_at.desc(), OrgMembership.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    membership = result.scalars().first()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active organization membership",
        )

    return membership


def require_org_role(*allowed_roles: str) -> Callable[..., Any]:
    """
    Dependency factory: checks the user's org_role.

    Usage:
        from app.core.roles import OrgRole

        @router.post("/invite")
        async def invite(
            membership = Depends(require_org_role(OrgRole.OWNER, OrgRole.ADMIN)),
        ):
            ...
    """

    async def _check_org_role(
        membership: OrgMembership = Depends(get_current_org_membership),
    ) -> OrgMembership:
        if membership.org_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient org permissions",
            )
        return membership

    return _check_org_role
