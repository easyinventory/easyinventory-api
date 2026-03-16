from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserResponse

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Return the current user's profile from the database.

    On first call, automatically creates the user record from
    the JWT claims. Subsequent calls return the existing record.
    """
    return current_user
