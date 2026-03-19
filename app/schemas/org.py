"""
Backward-compatibility shim — re-exports from app.orgs.schemas.

This file will be removed once all callers are updated.
"""

from app.orgs.schemas import (  # noqa: F401
    InviteMemberRequest,
    OrgMemberDetail,
    OrgMembershipResponse,
    OrgResponse,
    UpdateRoleRequest,
)
