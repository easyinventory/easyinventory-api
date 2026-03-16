from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.cognito import invite_cognito_user
from app.core.database import get_db
from app.models.organization import Organization
from app.models.user import User
from app.schemas.admin import CreateOrgRequest, OrgListItem
from app.services import org_service

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


@router.post("/orgs", response_model=OrgListItem, status_code=201)
async def create_org(
    body: CreateOrgRequest,
    current_user: User = Depends(require_role("SYSTEM_ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Create a new organization and assign an owner.

    If the owner email is unknown, creates a Cognito account
    (sends invite email) and a placeholder user.
    """
    # ── Create the org ──
    org = Organization(name=body.name)
    db.add(org)
    await db.flush()

    # ── Find or create the owner ──
    user = await org_service.find_user_by_email(db, body.owner_email)

    if user:
        # Check if they already own an org (optional guard)
        existing = await org_service.find_existing_membership(db, org.id, user.id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of this organization",
            )

        # Existing user → active ownership
        await org_service.create_membership(
            db=db,
            org_id=org.id,
            user_id=user.id,
            org_role="ORG_OWNER",
            is_active=True,
        )
    else:
        # New email → Cognito invite + placeholder
        invite_cognito_user(body.owner_email)
        placeholder = await org_service.create_placeholder_user(db, body.owner_email)
        await org_service.create_membership(
            db=db,
            org_id=org.id,
            user_id=placeholder.id,
            org_role="ORG_OWNER",
            is_active=False,
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
    current_user: User = Depends(require_role("SYSTEM_ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all organizations. System admin only."""
    return await org_service.list_all_orgs(db)
