from fastapi import APIRouter, Depends

from app.api.deps import require_role
from app.models.user import User

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/status")
async def admin_status(
    user: User = Depends(require_role("SYSTEM_ADMIN")),
) -> dict:
    """
    Admin-only endpoint for testing role enforcement.

    Returns 200 if the user is a SYSTEM_ADMIN.
    Returns 403 if they're not.
    """
    return {
        "message": "You are an admin",
        "email": user.email,
        "role": user.system_role,
    }
