"""
Centralized role constants for system-level and org-level roles.

Usage:
    from app.core.roles import SystemRole, OrgRole

    if user.system_role == SystemRole.ADMIN:
        ...

    require_role(SystemRole.ADMIN)
    require_org_role(OrgRole.OWNER, OrgRole.ADMIN)

These are plain string constants (not enums) so they stay compatible
with SQLAlchemy column defaults, Pydantic schemas, and existing DB
values without any migration.
"""


class SystemRole:
    ADMIN = "SYSTEM_ADMIN"
    USER = "SYSTEM_USER"

    ALL = (ADMIN, USER)


class OrgRole:
    OWNER = "ORG_OWNER"
    ADMIN = "ORG_ADMIN"
    EMPLOYEE = "ORG_EMPLOYEE"
    VIEWER = "ORG_VIEWER"

    ALL = (OWNER, ADMIN, EMPLOYEE, VIEWER)

    # Roles that can be assigned via invite (owner is never invited)
    INVITABLE = (ADMIN, EMPLOYEE, VIEWER)

    # Roles that can manage other members
    MANAGERS = (OWNER, ADMIN)
