from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from app.services.user_service import get_or_create_user
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
