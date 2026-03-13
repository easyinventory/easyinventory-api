from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/me")
async def get_me(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Return the current user's JWT claims.

    Requires a valid Bearer token in the Authorization header.
    This endpoint is useful for:
    - Verifying auth is working end-to-end
    - The frontend to fetch user info after login
    """
    return {
        "sub": current_user.get("sub"),
        "email": current_user.get("email"),
        "token_use": current_user.get("token_use"),
    }
