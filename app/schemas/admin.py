"""
Re-export shim — backwards-compatibility for ``from app.schemas.admin import ...``.

All schemas have moved to app.admin.schemas.
This file will be removed once all callers are updated.
"""

from app.admin.schemas import (  # noqa: F401
    CreateOrgRequest,
    OrgListItem,
    TransferOwnershipRequest,
    UpdateOrgRequest,
    UserListItem,
)
