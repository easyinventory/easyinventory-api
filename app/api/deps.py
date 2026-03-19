"""
Backward-compatibility shim — re-exports from new domain modules.

All functionality has moved to:
  - app.auth.deps  (get_current_user, require_role, bearer_scheme)
  - app.orgs.deps  (get_current_org_membership, require_org_role)

This file will be removed once all callers are updated.
"""

from app.auth.deps import (  # noqa: F401
    bearer_scheme,
    get_current_user,
    require_role,
)
from app.orgs.deps import (  # noqa: F401
    get_current_org_membership,
    require_org_role,
)
