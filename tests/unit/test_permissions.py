"""Tests for app.api.permissions — shared org permission helpers."""

import pytest
from unittest.mock import MagicMock

from app.api.permissions import (
    assert_admin_hierarchy,
    assert_can_assign_role,
    assert_not_owner,
    assert_valid_invite_role,
)
from app.core.exceptions import (
    AdminHierarchyViolation,
    InsufficientPermission,
    InvalidRole,
    OwnerProtected,
)
from app.core.roles import OrgRole
from app.models.org_membership import OrgMembership


def _mock_membership(role: str) -> MagicMock:
    mock = MagicMock(spec=OrgMembership)
    mock.org_role = role
    return mock


# ── assert_not_owner ──


def test_not_owner_passes_for_employee():
    target = _mock_membership(OrgRole.EMPLOYEE)
    assert_not_owner(target, "deactivate")  # should not raise


def test_not_owner_passes_for_admin():
    target = _mock_membership(OrgRole.ADMIN)
    assert_not_owner(target, "remove")  # should not raise


def test_not_owner_raises_for_owner():
    target = _mock_membership(OrgRole.OWNER)
    with pytest.raises(OwnerProtected) as exc_info:
        assert_not_owner(target, "deactivate")
    assert "deactivate" in exc_info.value.detail
    assert exc_info.value.status_code == 403


# ── assert_admin_hierarchy ──


def test_owner_can_modify_admin():
    assert_admin_hierarchy(OrgRole.OWNER, OrgRole.ADMIN, "remove")


def test_admin_cannot_modify_admin():
    with pytest.raises(AdminHierarchyViolation) as exc_info:
        assert_admin_hierarchy(OrgRole.ADMIN, OrgRole.ADMIN, "remove")
    assert "owner" in exc_info.value.detail.lower()
    assert "remove" in exc_info.value.detail


def test_admin_can_modify_employee():
    assert_admin_hierarchy(OrgRole.ADMIN, OrgRole.EMPLOYEE, "remove")


def test_admin_can_modify_viewer():
    assert_admin_hierarchy(OrgRole.ADMIN, OrgRole.VIEWER, "deactivate")


# ── assert_valid_invite_role ──


def test_valid_invite_roles():
    for role in OrgRole.INVITABLE:
        assert_valid_invite_role(role)  # should not raise


def test_owner_is_not_invitable():
    with pytest.raises(InvalidRole) as exc_info:
        assert_valid_invite_role(OrgRole.OWNER)
    assert exc_info.value.status_code == 400


def test_garbage_role_is_not_invitable():
    with pytest.raises(InvalidRole):
        assert_valid_invite_role("SUPER_ADMIN")


# ── assert_can_assign_role ──


def test_owner_can_assign_admin():
    assert_can_assign_role(OrgRole.OWNER, OrgRole.ADMIN)


def test_owner_can_assign_employee():
    assert_can_assign_role(OrgRole.OWNER, OrgRole.EMPLOYEE)


def test_admin_can_assign_employee():
    assert_can_assign_role(OrgRole.ADMIN, OrgRole.EMPLOYEE)


def test_admin_cannot_assign_admin():
    with pytest.raises(InsufficientPermission) as exc_info:
        assert_can_assign_role(OrgRole.ADMIN, OrgRole.ADMIN)
    assert "owner" in exc_info.value.detail.lower()


def test_nobody_can_assign_owner():
    with pytest.raises(InvalidRole) as exc_info:
        assert_can_assign_role(OrgRole.OWNER, OrgRole.OWNER)
    assert "Transfer ownership" in exc_info.value.detail
