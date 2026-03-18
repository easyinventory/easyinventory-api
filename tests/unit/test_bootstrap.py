"""Tests for app.core.bootstrap — startup seeder."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.bootstrap import run_bootstrap
from app.core.roles import OrgRole, SystemRole
from app.models.organization import Organization
from app.models.org_membership import OrgMembership
from app.models.user import User


def _seed_count_result(count: int = 0):
    """Mock result for the `SELECT count(*)` in _seed_sample_data."""
    result = MagicMock()
    result.scalar_one.return_value = count
    return result


def _mock_db_no_existing_user():
    """Mock DB where the bootstrap user does NOT exist yet."""
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    # First call: user lookup → None; second: seed count → 0;
    # subsequent calls return a generic mock (flush-related).
    mock_db.execute = AsyncMock(side_effect=[user_result, _seed_count_result(0)])
    return mock_db


def _mock_db_existing_user(email="admin@company.com", has_membership=True):
    """Mock DB where the bootstrap user already exists.

    If has_membership=False, the second execute() (membership check) returns None.
    """
    existing = MagicMock(spec=User)
    existing.id = uuid.uuid4()
    existing.email = email
    existing.system_role = SystemRole.ADMIN

    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = existing

    membership_result = MagicMock()
    if has_membership:
        mock_mem = MagicMock(spec=OrgMembership)
        membership_result.scalar_one_or_none.return_value = mock_mem
    else:
        membership_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    if has_membership:
        mock_db.execute = AsyncMock(
            side_effect=[user_result, membership_result, _seed_count_result(1)]
        )
    else:
        mock_db.execute = AsyncMock(
            side_effect=[user_result, membership_result, _seed_count_result(0)]
        )
    return mock_db


@patch("app.core.bootstrap.settings")
async def test_creates_placeholder_admin(mock_settings):
    """Bootstrap should create a placeholder user with SYSTEM_ADMIN role."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = "Default Organization"
    mock_db = _mock_db_no_existing_user()

    await run_bootstrap(mock_db)

    # First 3 adds are: user, org, membership (then seed data follows)
    assert mock_db.add.call_count >= 3

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
async def test_skips_when_user_already_exists_with_membership(mock_settings):
    """If user with that email exists AND has a membership, bootstrap skips creation but still checks seed."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = "Default Organization"
    mock_db = _mock_db_existing_user(has_membership=True)

    await run_bootstrap(mock_db)

    # No user/org/membership created; seed check runs but finds existing data
    mock_db.add.assert_not_called()


@patch("app.core.bootstrap.settings")
async def test_creates_org_when_user_exists_without_membership(mock_settings):
    """If user exists but has no membership, create org + membership."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = "My Company"
    mock_db = _mock_db_existing_user(has_membership=False)

    await run_bootstrap(mock_db)

    # First 2 adds are: org and membership (then seed data follows)
    assert mock_db.add.call_count >= 2

    org = mock_db.add.call_args_list[0][0][0]
    assert isinstance(org, Organization)
    assert org.name == "My Company"

    membership = mock_db.add.call_args_list[1][0][0]
    assert isinstance(membership, OrgMembership)
    assert membership.org_role == OrgRole.OWNER
    assert membership.is_active is True


@patch("app.core.bootstrap.settings")
async def test_promotes_existing_user_to_admin(mock_settings):
    """If user exists without membership and isn't admin, promote them."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = "Default Organization"

    # Build a user with SYSTEM_USER role manually
    existing = MagicMock(spec=User)
    existing.id = uuid.uuid4()
    existing.email = "admin@company.com"
    existing.system_role = "SYSTEM_USER"

    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = existing

    membership_result = MagicMock()
    membership_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute = AsyncMock(
        side_effect=[user_result, membership_result, _seed_count_result(0)]
    )

    await run_bootstrap(mock_db)

    assert existing.system_role == SystemRole.ADMIN


@patch("app.core.bootstrap.settings")
async def test_membership_active_when_user_already_exists(mock_settings):
    """When user already exists (real login), membership should be active."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = "Default Organization"
    mock_db = _mock_db_existing_user(has_membership=False)

    await run_bootstrap(mock_db)

    membership = mock_db.add.call_args_list[1][0][0]
    assert isinstance(membership, OrgMembership)
    assert membership.is_active is True


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
async def test_flushes_for_user_org_membership_and_seeds(mock_settings):
    """Bootstrap flushes for user, org, membership, plus seed data."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = "Default Organization"
    mock_db = _mock_db_no_existing_user()

    await run_bootstrap(mock_db)

    # 3 flushes for user/org/membership + 1 for suppliers + 2*N for products
    # (one flush per product create + one per product's links)
    # At minimum, more than 3 flushes
    assert mock_db.flush.call_count > 3


@patch("app.core.bootstrap.settings")
async def test_seeds_suppliers_and_products(mock_settings):
    """Bootstrap should seed suppliers, products, and product-supplier links."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = "Default Organization"
    mock_db = _mock_db_no_existing_user()

    await run_bootstrap(mock_db)

    from app.models.product import Product
    from app.models.product_supplier import ProductSupplier
    from app.models.supplier import Supplier

    added_items = [call[0][0] for call in mock_db.add.call_args_list]
    suppliers = [x for x in added_items if isinstance(x, Supplier)]
    products = [x for x in added_items if isinstance(x, Product)]
    links = [x for x in added_items if isinstance(x, ProductSupplier)]

    assert len(suppliers) == 4
    assert len(products) == 5
    assert len(links) > 0
    # Verify all links are active
    assert all(link.is_active is True for link in links)


@patch("app.core.bootstrap.settings")
async def test_seed_skips_when_suppliers_exist(mock_settings):
    """If suppliers already exist for the org, seeding is a no-op."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = "Default Organization"

    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    # Second execute returns count=3 (suppliers exist)
    mock_db.execute = AsyncMock(side_effect=[user_result, _seed_count_result(3)])

    await run_bootstrap(mock_db)

    from app.models.supplier import Supplier

    added_items = [call[0][0] for call in mock_db.add.call_args_list]
    suppliers = [x for x in added_items if isinstance(x, Supplier)]
    assert len(suppliers) == 0
