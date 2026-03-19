"""
Re-export shim — backwards-compatibility for ``from app.services import org_service``.

All logic has moved to:
  - app.orgs.service   (member CRUD)
  - app.admin.service  (system-admin org/user management)
  - app.users.service  (user lookups, placeholder creation)

This file will be removed once all callers are updated.
"""

from app.orgs.service import (  # noqa: F401
    list_org_members,
    get_membership_by_id,
    find_existing_membership,
    create_membership,
    update_role,
    set_active_status,
    delete_membership,
)

from app.admin.service import (  # noqa: F401
    list_all_orgs,
    get_org_by_id,
    rename_org,
    delete_org,
    transfer_ownership,
    list_all_users,
)

from app.users.service import (  # noqa: F401
    get_user_by_id,
    find_user_by_email,
    create_placeholder_user,
)
