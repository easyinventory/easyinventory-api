from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.database import get_db
from app.core.roles import OrgRole, SystemRole
from app.models.organization import Organization
from app.models.user import User
from app.schemas.admin import CreateOrgRequest, OrgListItem
from app.services import org_service
from app.services.invite_service import invite_user_to_org

router = APIRouter(prefix="/api/admin", tags=["admin"])


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
