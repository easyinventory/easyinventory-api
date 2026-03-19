"""
Re-export shim — backwards-compatibility for ``from app.services.user_service import ...``.

All logic has moved to app.users.service.
This file will be removed once all callers are updated.
"""

from app.users.service import (  # noqa: F401
    get_user_by_id,
    find_user_by_email,
    create_placeholder_user,
    get_or_create_user,
    delete_user_completely,
)
