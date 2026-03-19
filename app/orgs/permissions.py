"""
Shared permission helpers for org-level access control.

These raise domain exceptions (not HTTPException) so they can be
used from services, background jobs, or CLI commands — not just
route handlers. The AppError exception handler in main.py
translates them to HTTP responses automatically.
"""

from __future__ import annotations

from app.core.exceptions import (
    AdminHierarchyViolation,
    InsufficientPermission,
    InvalidRole,
    OwnerProtected,
)
from app.core.roles import OrgRole
from app.models.org_membership import OrgMembership


def assert_not_owner(target: OrgMembership, action: str) -> None:
    """Raise if the target is the org owner."""
    if target.org_role == OrgRole.OWNER:
        raise OwnerProtected(action)


def assert_admin_hierarchy(
    actor_role: str,
    target_role: str,
    action: str,
) -> None:
    """Raise if an admin tries to modify another admin (only owner can)."""
    if target_role == OrgRole.ADMIN and actor_role != OrgRole.OWNER:
        raise AdminHierarchyViolation(action)


def assert_valid_invite_role(role: str) -> None:
    """Raise if the role is not a valid invite target."""
    if role not in OrgRole.INVITABLE:
        raise InvalidRole(
            f"Invalid role. Must be one of: {', '.join(OrgRole.INVITABLE)}"
        )


def assert_can_assign_role(actor_role: str, target_role: str) -> None:
    """Raise if the actor can't assign the target role."""
    if target_role == OrgRole.OWNER:
        raise InvalidRole("Cannot assign ORG_OWNER. Transfer ownership instead.")
    if target_role == OrgRole.ADMIN and actor_role != OrgRole.OWNER:
        raise InsufficientPermission("Only the owner can assign admin roles")
