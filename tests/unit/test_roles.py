"""Tests for app.core.roles constants."""

from app.core.roles import SystemRole, OrgRole


def test_system_roles_are_strings():
    """Role constants must be plain strings for DB compatibility."""
    assert isinstance(SystemRole.ADMIN, str)
    assert isinstance(SystemRole.USER, str)


def test_org_roles_are_strings():
    assert isinstance(OrgRole.OWNER, str)
    assert isinstance(OrgRole.ADMIN, str)
    assert isinstance(OrgRole.EMPLOYEE, str)
    assert isinstance(OrgRole.VIEWER, str)


def test_system_role_values():
    assert SystemRole.ADMIN == "SYSTEM_ADMIN"
    assert SystemRole.USER == "SYSTEM_USER"


def test_org_role_values():
    assert OrgRole.OWNER == "ORG_OWNER"
    assert OrgRole.ADMIN == "ORG_ADMIN"
    assert OrgRole.EMPLOYEE == "ORG_EMPLOYEE"
    assert OrgRole.VIEWER == "ORG_VIEWER"


def test_system_all_contains_both():
    assert SystemRole.ADMIN in SystemRole.ALL
    assert SystemRole.USER in SystemRole.ALL
    assert len(SystemRole.ALL) == 2


def test_org_all_contains_all_four():
    assert OrgRole.OWNER in OrgRole.ALL
    assert OrgRole.ADMIN in OrgRole.ALL
    assert OrgRole.EMPLOYEE in OrgRole.ALL
    assert OrgRole.VIEWER in OrgRole.ALL
    assert len(OrgRole.ALL) == 4


def test_invitable_excludes_owner():
    """Owner can never be assigned via invite."""
    assert OrgRole.OWNER not in OrgRole.INVITABLE
    assert OrgRole.ADMIN in OrgRole.INVITABLE
    assert OrgRole.EMPLOYEE in OrgRole.INVITABLE
    assert OrgRole.VIEWER in OrgRole.INVITABLE


def test_managers_includes_owner_and_admin():
    assert OrgRole.OWNER in OrgRole.MANAGERS
    assert OrgRole.ADMIN in OrgRole.MANAGERS
    assert OrgRole.EMPLOYEE not in OrgRole.MANAGERS
    assert OrgRole.VIEWER not in OrgRole.MANAGERS


def test_user_model_default_uses_constant():
    """Verify the User model default matches our constant."""
    from app.models.user import User

    assert User.system_role.default.arg == SystemRole.USER
