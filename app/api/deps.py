from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.cognito import verify_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    """
    FastAPI dependency that extracts and validates the JWT.

    Usage in any route:
        @router.get("/something")
        async def something(user: dict = Depends(get_current_user)):
            print(user["sub"], user["email"])

    Returns decoded JWT claims on success.
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

    return claims
