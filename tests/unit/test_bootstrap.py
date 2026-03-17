"""Tests for app.core.bootstrap — startup seeder."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.bootstrap import run_bootstrap
from app.core.roles import OrgRole, SystemRole
from app.models.organization import Organization
from app.models.org_membership import OrgMembership
from app.models.user import User


def _mock_db_no_existing_user():
    """Mock DB where the bootstrap user does NOT exist yet."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute.return_value = mock_result
    return mock_db


def _mock_db_existing_user(email="admin@company.com"):
    """Mock DB where the bootstrap user already exists."""
    existing = MagicMock(spec=User)
    existing.email = email
    existing.system_role = SystemRole.ADMIN

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute.return_value = mock_result
    return mock_db


@patch("app.core.bootstrap.settings")
async def test_creates_placeholder_admin(mock_settings):
    """Bootstrap should create a placeholder user with SYSTEM_ADMIN role."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = "Default Organization"
    mock_db = _mock_db_no_existing_user()

    await run_bootstrap(mock_db)

    # Should add 3 things: user, org, membership
    assert mock_db.add.call_count == 3

    user = mock_db.add.call_args_list[0][0][0]
    assert isinstance(user, User)
    assert user.email == "admin@company.com"
    assert user.cognito_sub == "pending:admin@company.com"
    assert user.system_role == SystemRole.ADMIN
    assert user.is_active is False


@patch("app.core.bootstrap.settings")
async def test_creates_default_org(mock_settings):
    """Bootstrap should create an organization with the configured name."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = "My Company"
    mock_db = _mock_db_no_existing_user()

    await run_bootstrap(mock_db)

    org = mock_db.add.call_args_list[1][0][0]
    assert isinstance(org, Organization)
    assert org.name == "My Company"


@patch("app.core.bootstrap.settings")
async def test_creates_owner_membership(mock_settings):
    """Bootstrap should create an ORG_OWNER membership linking user to org."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = "Default Organization"
    mock_db = _mock_db_no_existing_user()

    await run_bootstrap(mock_db)

    membership = mock_db.add.call_args_list[2][0][0]
    assert isinstance(membership, OrgMembership)
    assert membership.org_role == OrgRole.OWNER
    assert membership.is_active is False


@patch("app.core.bootstrap.settings")
async def test_membership_inactive_until_login(mock_settings):
    """Membership should be inactive — activated when admin claims placeholder."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = "Default Organization"
    mock_db = _mock_db_no_existing_user()

    await run_bootstrap(mock_db)

    user = mock_db.add.call_args_list[0][0][0]
    membership = mock_db.add.call_args_list[2][0][0]
    assert user.is_active is False
    assert membership.is_active is False


@patch("app.core.bootstrap.settings")
async def test_skips_when_user_already_exists(mock_settings):
    """If user with that email exists, bootstrap is a no-op."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = "Default Organization"
    mock_db = _mock_db_existing_user()

    await run_bootstrap(mock_db)

    mock_db.add.assert_not_called()


@patch("app.core.bootstrap.settings")
async def test_skips_when_email_not_configured(mock_settings):
    """If BOOTSTRAP_ADMIN_EMAIL is empty, do nothing."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = ""
    mock_settings.BOOTSTRAP_ORG_NAME = "Default Organization"
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    await run_bootstrap(mock_db)

    mock_db.execute.assert_not_called()
    mock_db.add.assert_not_called()


@patch("app.core.bootstrap.settings")
async def test_email_is_lowercased(mock_settings):
    """Bootstrap should normalize email to lowercase."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "  Admin@Company.COM  "
    mock_settings.BOOTSTRAP_ORG_NAME = "Default Organization"
    mock_db = _mock_db_no_existing_user()

    await run_bootstrap(mock_db)

    user = mock_db.add.call_args_list[0][0][0]
    assert user.email == "admin@company.com"
    assert user.cognito_sub == "pending:admin@company.com"


@patch("app.core.bootstrap.settings")
async def test_default_org_name_fallback(mock_settings):
    """If BOOTSTRAP_ORG_NAME is empty, fall back to 'Default Organization'."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = ""
    mock_db = _mock_db_no_existing_user()

    await run_bootstrap(mock_db)

    org = mock_db.add.call_args_list[1][0][0]
    assert org.name == "Default Organization"


@patch("app.core.bootstrap.settings")
async def test_flushes_three_times(mock_settings):
    """Each entity (user, org, membership) should be flushed for ID generation."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = "Default Organization"
    mock_db = _mock_db_no_existing_user()

    await run_bootstrap(mock_db)

    assert mock_db.flush.call_count == 3
