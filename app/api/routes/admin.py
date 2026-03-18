import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.cognito import delete_cognito_user
from app.core.database import get_db
from app.core.roles import OrgRole, SystemRole
from app.models.organization import Organization
from app.models.user import User
from app.schemas.admin import CreateOrgRequest, OrgListItem, UserListItem
from app.schemas.org import OrgMemberDetail
from app.services import org_service
from app.services.invite_service import invite_user_to_org
from app.services.user_service import delete_user_completely

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Helpers ──


async def _get_org_or_404(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> None:
    org = await org_service.get_org_by_id(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")


@router.get("/status")
async def admin_status(
    user: User = Depends(require_role(SystemRole.ADMIN)),
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


@router.post("/orgs", response_model=OrgListItem, status_code=201)
async def create_org(
    body: CreateOrgRequest,
    current_user: User = Depends(require_role(SystemRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Create a new organization and assign an owner.

    If the owner email is unknown, creates a Cognito account
    (sends invite email) and a placeholder user.
    """
    org = Organization(name=body.name)
    db.add(org)
    await db.flush()

    await invite_user_to_org(
        db=db,
        org_id=org.id,
        email=body.owner_email,
        org_role=OrgRole.OWNER,
        is_new_org=True,
    )

    return {
        "id": org.id,
        "name": org.name,
        "created_at": org.created_at,
        "owner_email": body.owner_email,
        "member_count": 1,
    }


@router.get("/orgs", response_model=list[OrgListItem])
async def list_orgs(
    current_user: User = Depends(require_role(SystemRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all organizations. System admin only."""
    return await org_service.list_all_orgs(db)


# ── Org member introspection ──


@router.get("/orgs/{org_id}/members", response_model=list[OrgMemberDetail])
async def list_org_members(
    org_id: uuid.UUID,
    current_user: User = Depends(require_role(SystemRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all members of a specific org. System admin only."""
    await _get_org_or_404(db, org_id)
    return await org_service.list_org_members(db=db, org_id=org_id)


# ── User management ──


@router.get("/users", response_model=list[UserListItem])
async def list_users(
    current_user: User = Depends(require_role(SystemRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all users across all orgs. System admin only."""
    return await org_service.list_all_users(db)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_role(SystemRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a user from the local system and Cognito."""
    target = await org_service.get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.id == current_user.id:
        raise HTTPException(
            status_code=400, detail="You cannot delete your own account"
        )

    await delete_user_completely(db, target)
    delete_cognito_user(target.email, target.cognito_sub)
