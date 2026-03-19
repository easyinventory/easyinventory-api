from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from app.auth.deps import get_current_user
from app.orgs.deps import (
    get_current_org_membership,
    RequireOrgRole,
)
from app.orgs.permissions import (
    assert_admin_hierarchy,
    assert_can_assign_role,
    assert_not_owner,
    assert_valid_invite_role,
)
from app.core.database import get_db
from app.core.roles import OrgRole
from app.models.user import User
from app.models.org_membership import OrgMembership
from app.orgs.schemas import (
    OrgMembershipResponse,
    OrgMemberDetail,
    InviteMemberRequest,
    UpdateRoleRequest,
)
from app.orgs import service as org_service
from app.invites.service import invite_user_to_org

router = APIRouter(prefix="/api/orgs", tags=["organizations"])


# ── Internal helpers ──


async def _get_target_or_404(
    db: AsyncSession,
    member_id: uuid.UUID,
    org_id: uuid.UUID,
) -> OrgMembership:
    target = await org_service.get_membership_by_id(db, member_id, org_id)
    if not target:
        raise HTTPException(
            status_code=404,
            detail="Membership not found",
        )
    return target


# ── Endpoints ──


@router.get("/me", response_model=list[OrgMembershipResponse])
async def get_my_orgs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[OrgMembership]:
    """Return the current user's org memberships."""
    stmt = (
        select(OrgMembership)
        .where(OrgMembership.user_id == current_user.id)
        .where(OrgMembership.is_active == True)  # noqa: E712
        .options(selectinload(OrgMembership.organization))
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/members", response_model=list[OrgMemberDetail])
async def list_members(
    membership: OrgMembership = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db),
) -> list[OrgMembership]:
    """List all members of the current user's org."""
    return await org_service.list_org_members(db=db, org_id=membership.org_id)


@router.post("/invite", response_model=OrgMemberDetail, status_code=201)
async def invite_member(
    body: InviteMemberRequest,
    membership: OrgMembership = Depends(
        RequireOrgRole(OrgRole.OWNER, OrgRole.ADMIN),
    ),
    db: AsyncSession = Depends(get_db),
) -> OrgMembership:
    """Invite a user to the org by email."""
    assert_valid_invite_role(body.org_role)
    assert_can_assign_role(membership.org_role, body.org_role)

    return await invite_user_to_org(
        db=db,
        org_id=membership.org_id,
        email=body.email,
        org_role=body.org_role,
    )


@router.patch("/members/{member_id}/role", response_model=OrgMemberDetail)
async def update_role(
    member_id: uuid.UUID,
    body: UpdateRoleRequest,
    membership: OrgMembership = Depends(
        RequireOrgRole(OrgRole.OWNER, OrgRole.ADMIN),
    ),
    db: AsyncSession = Depends(get_db),
) -> OrgMembership:
    """Change a member's org role."""
    target = await _get_target_or_404(db, member_id, membership.org_id)

    assert_valid_invite_role(body.org_role)
    assert_not_owner(target, "change role of")
    assert_admin_hierarchy(membership.org_role, target.org_role, "change role of")
    assert_can_assign_role(membership.org_role, body.org_role)

    return await org_service.update_role(db, target, body.org_role)


@router.patch("/members/{member_id}/deactivate", response_model=OrgMemberDetail)
async def deactivate_member(
    member_id: uuid.UUID,
    membership: OrgMembership = Depends(
        RequireOrgRole(OrgRole.OWNER, OrgRole.ADMIN),
    ),
    db: AsyncSession = Depends(get_db),
) -> OrgMembership:
    """Deactivate a member."""
    target = await _get_target_or_404(db, member_id, membership.org_id)

    assert_not_owner(target, "deactivate")
    assert_admin_hierarchy(membership.org_role, target.org_role, "deactivate")

    return await org_service.set_active_status(db, target, is_active=False)


@router.patch("/members/{member_id}/activate", response_model=OrgMemberDetail)
async def activate_member(
    member_id: uuid.UUID,
    membership: OrgMembership = Depends(
        RequireOrgRole(OrgRole.OWNER, OrgRole.ADMIN),
    ),
    db: AsyncSession = Depends(get_db),
) -> OrgMembership:
    """Reactivate a deactivated member."""
    target = await _get_target_or_404(db, member_id, membership.org_id)

    return await org_service.set_active_status(db, target, is_active=True)


@router.delete("/members/{member_id}", status_code=204)
async def remove_member(
    member_id: uuid.UUID,
    membership: OrgMembership = Depends(
        RequireOrgRole(OrgRole.OWNER, OrgRole.ADMIN),
    ),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a member from the org entirely."""
    target = await _get_target_or_404(db, member_id, membership.org_id)

    assert_not_owner(target, "remove")
    assert_admin_hierarchy(membership.org_role, target.org_role, "remove")

    await org_service.delete_membership(db, target)
