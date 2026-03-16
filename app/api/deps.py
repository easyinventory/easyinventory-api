from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cognito import verify_token
from app.core.database import get_db
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

    user = await get_or_create_user(
        db=db,
        cognito_sub=claims["sub"],
        email=claims.get("email", ""),
    )

    return user


def require_role(*allowed_roles: str) -> Callable[..., Any]:
    """
    Dependency factory that checks the user's system_role.

    Usage:
        @router.get("/admin-only")
        async def admin_only(
            user: User = Depends(require_role("SYSTEM_ADMIN")),
        ):
            ...

        @router.get("/admin-or-user")
        async def admin_or_user(
            user: User = Depends(require_role("SYSTEM_ADMIN", "SYSTEM_USER")),
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
