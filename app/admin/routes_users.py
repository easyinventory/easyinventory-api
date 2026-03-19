"""
Admin user routes — system-admin user management endpoints.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import service as admin_service
from app.admin.schemas import UserListItem
from app.auth.cognito_admin import delete_cognito_user
from app.auth.deps import RequireRole
from app.core.database import get_db
from app.core.roles import SystemRole
from app.models.user import User
from app.users import service as user_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=list[UserListItem])
async def list_users(
    current_user: User = Depends(RequireRole(SystemRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[UserListItem]:
    """List all users across all orgs. System admin only."""
    users = await admin_service.list_all_users(db)
    return [
        UserListItem(
            id=user.id,
            email=user.email,
            system_role=user.system_role,
            is_active=user.is_active,
            created_at=user.created_at,
            org_count=len([m for m in user.memberships if m.is_active]),
        )
        for user in users
    ]


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    current_user: User = Depends(RequireRole(SystemRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a user from the local system and Cognito."""
    target = await user_service.get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.id == current_user.id:
        raise HTTPException(
            status_code=400, detail="You cannot delete your own account"
        )

    await user_service.delete_user_completely(db, target)
    await db.commit()
    delete_cognito_user(target.email, target.cognito_sub)
