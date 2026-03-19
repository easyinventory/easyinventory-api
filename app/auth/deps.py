from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.cognito_token import get_email_from_access_token, verify_token
from app.core.database import get_db
from app.models.user import User
from app.users.service import get_or_create_user

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


class RequireRole:
    """
    Callable dependency that checks the user's system_role.

    Usage::

        from app.core.roles import SystemRole

        @router.get("/admin-only")
        async def admin_only(
            user: User = Depends(RequireRole(SystemRole.ADMIN)),
        ):
            ...

    Returns the User if they have one of the allowed roles.
    Raises 403 if they don't.
    """

    def __init__(self, *allowed_roles: str):
        self.allowed_roles = allowed_roles

    async def __call__(
        self,
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.system_role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
