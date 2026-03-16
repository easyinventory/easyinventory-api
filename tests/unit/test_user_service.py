from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from app.services.user_service import get_or_create_user
from app.models.org_membership import OrgMembership
from app.models.user import User


async def test_returns_existing_user():
    """If user exists, return them without creating a new one."""
    existing_user = MagicMock(spec=User)
    existing_user.cognito_sub = "sub-123"
    existing_user.email = "existing@test.com"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_user

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    user = await get_or_create_user(
        db=mock_db,
        cognito_sub="sub-123",
        email="existing@test.com",
    )

    assert user == existing_user
    mock_db.add.assert_not_called()
    mock_db.flush.assert_not_called()


async def test_creates_new_user_when_not_found():
    """If user doesn't exist, create one with SYSTEM_USER role."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    user = await get_or_create_user(
        db=mock_db,
        cognito_sub="new-sub-456",
        email="newuser@test.com",
    )

    mock_db.add.assert_called_once()
    mock_db.flush.assert_called_once()

    # Verify the user that was added
    added_user = mock_db.add.call_args[0][0]
    assert added_user.cognito_sub == "new-sub-456"
    assert added_user.email == "newuser@test.com"
    assert added_user.system_role == "SYSTEM_USER"


async def test_new_user_gets_system_user_role():
    """Default role should be SYSTEM_USER, not admin."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    await get_or_create_user(
        db=mock_db,
        cognito_sub="sub-789",
        email="regular@test.com",
    )

    added_user = mock_db.add.call_args[0][0]
    assert added_user.system_role == "SYSTEM_USER"


async def test_does_not_duplicate_existing_user():
    """Second call with same sub should not create another user."""
    existing_user = MagicMock(spec=User)
    existing_user.cognito_sub = "sub-123"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_user

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    # Call twice with same sub
    user1 = await get_or_create_user(mock_db, "sub-123", "user@test.com")
    user2 = await get_or_create_user(mock_db, "sub-123", "user@test.com")

    assert user1 == user2
    mock_db.add.assert_not_called()


@patch("app.services.user_service.settings")
async def test_bootstrap_email_gets_admin_role(mock_settings):
    """User matching BOOTSTRAP_ADMIN_EMAIL gets SYSTEM_ADMIN."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute.return_value = mock_result

    from app.services.user_service import get_or_create_user

    await get_or_create_user(
        db=mock_db,
        cognito_sub="admin-sub",
        email="admin@company.com",
    )

    added_user = mock_db.add.call_args_list[0][0][0]
    assert added_user.system_role == "SYSTEM_ADMIN"


@patch("app.services.user_service.settings")
async def test_non_bootstrap_email_gets_user_role(mock_settings):
    """Regular user should NOT get SYSTEM_ADMIN."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute.return_value = mock_result

    from app.services.user_service import get_or_create_user

    await get_or_create_user(
        db=mock_db,
        cognito_sub="regular-sub",
        email="regular@company.com",
    )

    added_user = mock_db.add.call_args[0][0]
    assert added_user.system_role == "SYSTEM_USER"


@patch("app.services.user_service.settings")
async def test_bootstrap_email_case_insensitive(mock_settings):
    """Bootstrap email check should be case-insensitive."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "Admin@Company.com"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute.return_value = mock_result

    from app.services.user_service import get_or_create_user

    await get_or_create_user(
        db=mock_db,
        cognito_sub="admin-sub",
        email="admin@company.com",
    )

    added_user = mock_db.add.call_args_list[0][0][0]
    assert added_user.system_role == "SYSTEM_ADMIN"


@patch("app.services.user_service.settings")
async def test_empty_bootstrap_email_no_admin(mock_settings):
    """If BOOTSTRAP_ADMIN_EMAIL is empty, nobody gets admin."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = ""

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute.return_value = mock_result

    from app.services.user_service import get_or_create_user

    await get_or_create_user(
        db=mock_db,
        cognito_sub="any-sub",
        email="anyone@company.com",
    )

    added_user = mock_db.add.call_args[0][0]
    assert added_user.system_role == "SYSTEM_USER"


@patch("app.services.user_service.settings")
async def test_existing_user_role_not_changed(mock_settings):
    """If user already exists, their role should NOT be updated."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"

    existing_user = MagicMock()
    existing_user.cognito_sub = "admin-sub"
    existing_user.system_role = "SYSTEM_USER"  # was created before bootstrap was set

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_user

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    from app.services.user_service import get_or_create_user

    user = await get_or_create_user(
        db=mock_db,
        cognito_sub="admin-sub",
        email="admin@company.com",
    )

    # Should return existing user without changing role
    assert user.system_role == "SYSTEM_USER"
    mock_db.add.assert_not_called()


@patch("app.services.user_service.create_default_org")
@patch("app.services.user_service.settings")
async def test_admin_triggers_org_creation(mock_settings, mock_create_org):
    """Bootstrap admin creation should trigger create_default_org."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_create_org.return_value = MagicMock()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute.return_value = mock_result

    from app.services.user_service import get_or_create_user

    await get_or_create_user(
        db=mock_db,
        cognito_sub="admin-sub",
        email="admin@company.com",
    )

    mock_create_org.assert_called_once()


@patch("app.services.user_service.create_default_org")
@patch("app.services.user_service.settings")
async def test_regular_user_does_not_trigger_org_creation(
    mock_settings, mock_create_org
):
    """Regular user should NOT create an org."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute.return_value = mock_result

    from app.services.user_service import get_or_create_user

    await get_or_create_user(
        db=mock_db,
        cognito_sub="regular-sub",
        email="regular@company.com",
    )

    mock_create_org.assert_not_called()


@patch("app.services.user_service.settings")
async def test_placeholder_claimed_on_first_login(mock_settings):
    """Invited user logging in claims their placeholder."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = ""

    placeholder = MagicMock(spec=User)
    placeholder.id = uuid.uuid4()
    placeholder.cognito_sub = "pending:invited@test.com"
    placeholder.email = "invited@test.com"
    placeholder.is_active = False

    # Query 1: by cognito_sub → not found
    sub_result = MagicMock()
    sub_result.scalar_one_or_none.return_value = None

    # Query 2: by email + pending → found placeholder
    email_result = MagicMock()
    email_result.scalar_one_or_none.return_value = placeholder

    # Query 3: inactive memberships → one found
    mock_membership = MagicMock(spec=OrgMembership)
    mock_membership.is_active = False
    membership_result = MagicMock()
    membership_result.scalars.return_value.all.return_value = [mock_membership]

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute.side_effect = [sub_result, email_result, membership_result]

    from app.services.user_service import get_or_create_user

    user = await get_or_create_user(
        db=mock_db,
        cognito_sub="real-sub-123",
        email="invited@test.com",
    )

    assert user == placeholder
    assert user.cognito_sub == "real-sub-123"
    assert user.is_active is True
    assert mock_membership.is_active is True
    mock_db.add.assert_not_called()


@patch("app.services.user_service.settings")
async def test_placeholder_activates_multiple_memberships(mock_settings):
    """Claiming placeholder activates ALL their org memberships."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = ""

    placeholder = MagicMock(spec=User)
    placeholder.id = uuid.uuid4()
    placeholder.cognito_sub = "pending:multi@test.com"
    placeholder.email = "multi@test.com"
    placeholder.is_active = False

    sub_result = MagicMock()
    sub_result.scalar_one_or_none.return_value = None

    email_result = MagicMock()
    email_result.scalar_one_or_none.return_value = placeholder

    m1 = MagicMock(spec=OrgMembership)
    m1.is_active = False
    m2 = MagicMock(spec=OrgMembership)
    m2.is_active = False
    membership_result = MagicMock()
    membership_result.scalars.return_value.all.return_value = [m1, m2]

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute.side_effect = [sub_result, email_result, membership_result]

    from app.services.user_service import get_or_create_user

    await get_or_create_user(
        db=mock_db,
        cognito_sub="real-sub-456",
        email="multi@test.com",
    )

    assert m1.is_active is True
    assert m2.is_active is True


@patch("app.services.user_service.settings")
async def test_no_placeholder_creates_new_user(mock_settings):
    """If no placeholder exists, creates a new user normally."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = ""

    # Query 1: by cognito_sub → not found
    sub_result = MagicMock()
    sub_result.scalar_one_or_none.return_value = None

    # Query 2: by email + pending → not found
    email_result = MagicMock()
    email_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute.side_effect = [sub_result, email_result]

    from app.services.user_service import get_or_create_user

    await get_or_create_user(
        db=mock_db,
        cognito_sub="brand-new-sub",
        email="brand@new.com",
    )

    mock_db.add.assert_called_once()
    added = mock_db.add.call_args[0][0]
    assert isinstance(added, User)
    assert added.cognito_sub == "brand-new-sub"
    assert added.email == "brand@new.com"
