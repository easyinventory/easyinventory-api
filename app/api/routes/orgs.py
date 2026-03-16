from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from app.api.deps import (
    get_current_user,
    get_current_org_membership,
    require_org_role,
)
from app.core.database import get_db
from app.models.user import User
from app.models.org_membership import OrgMembership
from app.schemas.org import (
    OrgMembershipResponse,
    OrgMemberDetail,
    InviteMemberRequest,
    UpdateRoleRequest,
)
from app.services import org_service

router = APIRouter(prefix="/api/orgs", tags=["organizations"])

VALID_INVITE_ROLES = ("ORG_ADMIN", "ORG_EMPLOYEE", "ORG_VIEWER")


# ── Permission helpers ──


def _assert_not_owner(target: OrgMembership, action: str) -> None:
    """Nobody can deactivate/remove/change the owner."""
    if target.org_role == "ORG_OWNER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cannot {action} the organization owner",
        )


def _assert_admin_hierarchy(
    actor_role: str,
    target_role: str,
    action: str,
) -> None:
    """Admin can't modify another admin — only owner can."""
    if target_role == "ORG_ADMIN" and actor_role != "ORG_OWNER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only the owner can {action} an admin",
        )


def _assert_valid_role(role: str) -> None:
    if role not in VALID_INVITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {', '.join(VALID_INVITE_ROLES)}",
        )


def _assert_can_assign_role(actor_role: str, target_role: str) -> None:
    if target_role == "ORG_OWNER":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign ORG_OWNER. Transfer ownership instead.",
        )
    if target_role == "ORG_ADMIN" and actor_role != "ORG_OWNER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can assign admin roles",
        )


async def _get_target_or_404(
    db: AsyncSession,
    member_id: uuid.UUID,
    org_id: uuid.UUID,
) -> OrgMembership:
    target = await org_service.get_membership_by_id(db, member_id, org_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )
    return target


async def _member_detail(
    db: AsyncSession,
    membership: OrgMembership,
    email: str | None = None,
) -> dict:
    if not email:
        user = await org_service.get_user_by_id(db, membership.user_id)
        email = user.email if user else ""
    return {
        "id": membership.id,
        "user_id": membership.user_id,
        "email": email,
        "org_role": membership.org_role,
        "is_active": membership.is_active,
        "joined_at": membership.joined_at,
    }


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
) -> list[dict]:
    """List all members of the current user's org."""
    return await org_service.list_org_members(db=db, org_id=membership.org_id)


@router.post("/invite", response_model=OrgMemberDetail, status_code=201)
async def invite_member(
    body: InviteMemberRequest,
    membership: OrgMembership = Depends(
        require_org_role("ORG_OWNER", "ORG_ADMIN"),
    ),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Invite a user to the org by email."""
    # ── Permission checks ──
    _assert_valid_role(body.org_role)
    _assert_can_assign_role(membership.org_role, body.org_role)

    # ── Check for existing user ──
    existing_user = await org_service.find_user_by_email(db, body.email)

    if existing_user:
        # Check if already a member (active or inactive/pending)
        existing_membership = await org_service.find_existing_membership(
            db,
            membership.org_id,
            existing_user.id,
        )
        if existing_membership:
            # Distinguish between active member and pending invite
            if existing_membership.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User is already a member of this organization",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This user has already been invited. They will gain access when they sign up.",
                )

        # Known user, not yet a member → active membership
        new_membership = await org_service.create_membership(
            db=db,
            org_id=membership.org_id,
            user_id=existing_user.id,
            org_role=body.org_role,
            is_active=True,
        )
    else:
        # Unknown email → placeholder user + inactive membership
        placeholder = await org_service.create_placeholder_user(db, body.email)
        new_membership = await org_service.create_membership(
            db=db,
            org_id=membership.org_id,
            user_id=placeholder.id,
            org_role=body.org_role,
            is_active=False,
        )

    return await _member_detail(db, new_membership, email=body.email)


@router.patch("/members/{member_id}/role", response_model=OrgMemberDetail)
async def update_role(
    member_id: uuid.UUID,
    body: UpdateRoleRequest,
    membership: OrgMembership = Depends(
        require_org_role("ORG_OWNER", "ORG_ADMIN"),
    ),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Change a member's org role."""
    target = await _get_target_or_404(db, member_id, membership.org_id)

    # ── Permission checks ──
    _assert_valid_role(body.org_role)
    _assert_not_owner(target, "change role of")
    _assert_admin_hierarchy(membership.org_role, target.org_role, "change role of")
    _assert_can_assign_role(membership.org_role, body.org_role)

    # ── Business logic ──
    updated = await org_service.update_role(db, target, body.org_role)
    return await _member_detail(db, updated)


@router.patch("/members/{member_id}/deactivate", response_model=OrgMemberDetail)
async def deactivate_member(
    member_id: uuid.UUID,
    membership: OrgMembership = Depends(
        require_org_role("ORG_OWNER", "ORG_ADMIN"),
    ),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Deactivate a member."""
    target = await _get_target_or_404(db, member_id, membership.org_id)

    # ── Permission checks ──
    _assert_not_owner(target, "deactivate")
    _assert_admin_hierarchy(membership.org_role, target.org_role, "deactivate")

    # ── Business logic ──
    updated = await org_service.set_active_status(db, target, is_active=False)
    return await _member_detail(db, updated)


@router.patch("/members/{member_id}/activate", response_model=OrgMemberDetail)
async def activate_member(
    member_id: uuid.UUID,
    membership: OrgMembership = Depends(
        require_org_role("ORG_OWNER", "ORG_ADMIN"),
    ),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reactivate a deactivated member."""
    target = await _get_target_or_404(db, member_id, membership.org_id)

    updated = await org_service.set_active_status(db, target, is_active=True)
    return await _member_detail(db, updated)


@router.delete("/members/{member_id}", status_code=204)
async def remove_member(
    member_id: uuid.UUID,
    membership: OrgMembership = Depends(
        require_org_role("ORG_OWNER", "ORG_ADMIN"),
    ),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a member from the org entirely."""
    target = await _get_target_or_404(db, member_id, membership.org_id)

    # ── Permission checks ──
    _assert_not_owner(target, "remove")
    _assert_admin_hierarchy(membership.org_role, target.org_role, "remove")

    # ── Business logic ──
    await org_service.delete_membership(db, target)
