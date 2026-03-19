"""
Admin org routes — system-admin organization CRUD and member introspection.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import service as admin_service
from app.admin.schemas import (
    CreateOrgRequest,
    OrgListItem,
    TransferOwnershipRequest,
    UpdateOrgRequest,
)
from app.auth.deps import require_role
from app.core.database import get_db
from app.core.roles import OrgRole, SystemRole
from app.models.organization import Organization
from app.models.user import User
from app.orgs import service as org_service
from app.orgs.schemas import OrgMemberDetail
from app.services.invite_service import invite_user_to_org
from app.users import service as user_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Helpers ──


async def _get_org_or_404(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> Organization:
    org = await admin_service.get_org_by_id(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


# ── Status ──


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


# ── Organization CRUD ──


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
    return await admin_service.list_all_orgs(db)


@router.patch("/orgs/{org_id}", response_model=OrgListItem)
async def rename_org(
    org_id: uuid.UUID,
    body: UpdateOrgRequest,
    current_user: User = Depends(require_role(SystemRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Rename an organization. System admin only."""
    org = await _get_org_or_404(db, org_id)
    org = await admin_service.rename_org(db, org, body.name)

    # Re-fetch owner info for the response
    all_orgs = await admin_service.list_all_orgs(db)
    matched = next((o for o in all_orgs if o["id"] == org.id), None)
    return matched or {
        "id": org.id,
        "name": org.name,
        "created_at": org.created_at,
        "owner_email": None,
        "member_count": 0,
    }


@router.delete("/orgs/{org_id}", status_code=204)
async def delete_org(
    org_id: uuid.UUID,
    current_user: User = Depends(require_role(SystemRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an organization and all its memberships. System admin only."""
    org = await _get_org_or_404(db, org_id)
    await admin_service.delete_org(db, org)


@router.post("/orgs/{org_id}/transfer-ownership", response_model=OrgMemberDetail)
async def transfer_ownership(
    org_id: uuid.UUID,
    body: TransferOwnershipRequest,
    current_user: User = Depends(require_role(SystemRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Transfer org ownership to another member. System admin only."""
    await _get_org_or_404(db, org_id)

    new_owner_membership = await admin_service.transfer_ownership(
        db,
        org_id,
        body.new_owner_email,
    )

    user = await user_service.get_user_by_id(db, new_owner_membership.user_id)
    return {
        "id": new_owner_membership.id,
        "user_id": new_owner_membership.user_id,
        "email": user.email if user else "",
        "org_role": new_owner_membership.org_role,
        "is_active": new_owner_membership.is_active,
        "joined_at": new_owner_membership.joined_at,
    }


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
