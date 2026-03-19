"""Tests for app.services.user_service — user provisioning + placeholder claiming."""

from unittest.mock import AsyncMock, MagicMock
import uuid

from app.users.service import delete_user_completely, get_or_create_user
from app.core.roles import SystemRole
from app.models.org_membership import OrgMembership
from app.models.user import User

# ── Deletion ──


async def test_delete_user_completely_removes_memberships_and_user():
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()

    mock_db = AsyncMock()

    await delete_user_completely(mock_db, user)

    mock_db.execute.assert_awaited_once()
    mock_db.delete.assert_awaited_once_with(user)
    mock_db.flush.assert_awaited_once()


# ── Existing user lookup ──


async def test_returns_existing_user():
    """If user exists by cognito_sub, return them without creating."""
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


async def test_does_not_duplicate_existing_user():
    """Second call with same sub should not create another user."""
    existing_user = MagicMock(spec=User)
    existing_user.cognito_sub = "sub-123"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_user

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    user1 = await get_or_create_user(mock_db, "sub-123", "user@test.com")
    user2 = await get_or_create_user(mock_db, "sub-123", "user@test.com")

    assert user1 == user2
    mock_db.add.assert_not_called()


async def test_existing_user_role_not_changed():
    """If user already exists, their role should NOT be updated."""
    existing_user = MagicMock(spec=User)
    existing_user.cognito_sub = "admin-sub"
    existing_user.system_role = SystemRole.USER

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_user

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    user = await get_or_create_user(
        db=mock_db,
        cognito_sub="admin-sub",
        email="admin@company.com",
    )

    assert user.system_role == SystemRole.USER
    mock_db.add.assert_not_called()


# ── New user creation ──


async def test_creates_new_user_when_not_found():
    """If user doesn't exist and no placeholder, create SYSTEM_USER."""
    # Query 1: by cognito_sub → not found
    sub_result = MagicMock()
    sub_result.scalar_one_or_none.return_value = None

    # Query 2: by email + pending → not found
    email_result = MagicMock()
    email_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute.side_effect = [sub_result, email_result]

    user = await get_or_create_user(
        db=mock_db,
        cognito_sub="new-sub-456",
        email="newuser@test.com",
    )

    mock_db.add.assert_called_once()
    mock_db.flush.assert_called_once()

    added_user = mock_db.add.call_args[0][0]
    assert added_user.cognito_sub == "new-sub-456"
    assert added_user.email == "newuser@test.com"
    assert added_user.system_role == SystemRole.USER


async def test_new_user_always_gets_system_user_role():
    """All new users get SYSTEM_USER — admin is handled by bootstrap seeder."""
    sub_result = MagicMock()
    sub_result.scalar_one_or_none.return_value = None

    email_result = MagicMock()
    email_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute.side_effect = [sub_result, email_result]

    await get_or_create_user(
        db=mock_db,
        cognito_sub="sub-789",
        email="anyone@test.com",
    )

    added_user = mock_db.add.call_args[0][0]
    assert added_user.system_role == SystemRole.USER


async def test_new_user_does_not_create_org():
    """New users should never trigger org creation (bootstrap handles it)."""
    sub_result = MagicMock()
    sub_result.scalar_one_or_none.return_value = None

    email_result = MagicMock()
    email_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute.side_effect = [sub_result, email_result]

    await get_or_create_user(
        db=mock_db,
        cognito_sub="sub-any",
        email="any@test.com",
    )

    # Only one add call (the user), no org or membership
    mock_db.add.assert_called_once()
    added = mock_db.add.call_args[0][0]
    assert isinstance(added, User)


# ── Placeholder claiming ──


async def test_placeholder_claimed_on_first_login():
    """Invited user logging in claims their placeholder."""
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


async def test_placeholder_activates_multiple_memberships():
    """Claiming placeholder activates ALL their org memberships."""
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

    await get_or_create_user(
        db=mock_db,
        cognito_sub="real-sub-456",
        email="multi@test.com",
    )

    assert m1.is_active is True
    assert m2.is_active is True


async def test_no_placeholder_creates_new_user():
    """If no placeholder exists, creates a new user normally."""
    sub_result = MagicMock()
    sub_result.scalar_one_or_none.return_value = None

    email_result = MagicMock()
    email_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute.side_effect = [sub_result, email_result]

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
