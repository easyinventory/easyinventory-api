import uuid
from unittest.mock import AsyncMock, MagicMock

from app.orgs.service import (
    create_membership,
    update_role,
    set_active_status,
    delete_membership,
    find_existing_membership,
)
from app.users.service import (
    create_placeholder_user,
    find_user_by_email,
)
from app.models.user import User
from app.models.org_membership import OrgMembership


async def test_create_membership():
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    await create_membership(
        db=mock_db,
        org_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        org_role="ORG_EMPLOYEE",
        is_active=True,
    )

    added = mock_db.add.call_args[0][0]
    assert isinstance(added, OrgMembership)
    assert added.org_role == "ORG_EMPLOYEE"
    assert added.is_active is True


async def test_create_inactive_membership():
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    await create_membership(
        db=mock_db,
        org_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        org_role="ORG_EMPLOYEE",
        is_active=False,
    )

    added = mock_db.add.call_args[0][0]
    assert added.is_active is False


async def test_create_placeholder_user():
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    await create_placeholder_user(mock_db, "new@test.com")

    added = mock_db.add.call_args[0][0]
    assert isinstance(added, User)
    assert added.email == "new@test.com"
    assert added.cognito_sub == "pending:new@test.com"
    assert added.is_active is False


async def test_update_role_changes_role():
    membership = MagicMock(spec=OrgMembership)
    membership.org_role = "ORG_EMPLOYEE"
    mock_db = AsyncMock()

    await update_role(mock_db, membership, "ORG_ADMIN")
    assert membership.org_role == "ORG_ADMIN"


async def test_set_active_false():
    membership = MagicMock(spec=OrgMembership)
    membership.is_active = True
    mock_db = AsyncMock()

    await set_active_status(mock_db, membership, is_active=False)
    assert membership.is_active is False


async def test_set_active_true():
    membership = MagicMock(spec=OrgMembership)
    membership.is_active = False
    mock_db = AsyncMock()

    await set_active_status(mock_db, membership, is_active=True)
    assert membership.is_active is True


async def test_delete_membership_calls_delete():
    membership = MagicMock(spec=OrgMembership)
    mock_db = AsyncMock()

    await delete_membership(mock_db, membership)
    mock_db.delete.assert_called_once_with(membership)


async def test_find_user_returns_none():
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    result = await find_user_by_email(mock_db, "nobody@test.com")
    assert result is None


async def test_find_user_returns_user():
    existing = MagicMock(spec=User)
    existing.email = "found@test.com"
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    result = await find_user_by_email(mock_db, "found@test.com")
    assert result == existing


async def test_find_existing_membership_returns_none():
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    result = await find_existing_membership(mock_db, uuid.uuid4(), uuid.uuid4())
    assert result is None


async def test_find_existing_membership_returns_match():
    existing = MagicMock(spec=OrgMembership)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    result = await find_existing_membership(mock_db, uuid.uuid4(), uuid.uuid4())
    assert result == existing
