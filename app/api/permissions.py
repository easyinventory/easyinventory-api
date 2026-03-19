"""
Backward-compatibility shim — re-exports from app.orgs.permissions.

This file will be removed once all callers are updated.
"""

from app.orgs.permissions import (  # noqa: F401
    assert_admin_hierarchy,
    assert_can_assign_role,
    assert_not_owner,
    assert_valid_invite_role,
)
