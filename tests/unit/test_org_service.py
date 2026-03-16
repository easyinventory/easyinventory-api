import uuid
from unittest.mock import AsyncMock, MagicMock

from app.services.org_service import create_default_org
from app.models.organization import Organization
from app.models.org_membership import OrgMembership


async def test_creates_org_and_membership():
    """First call creates an org and adds user as ORG_OWNER."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute.return_value = mock_result

    owner_id = uuid.uuid4()
    await create_default_org(db=mock_db, owner_id=owner_id)

    # Should have called add twice: once for org, once for membership
    assert mock_db.add.call_count == 2
    assert mock_db.flush.call_count == 2

    # First add should be an Organization
    first_add = mock_db.add.call_args_list[0][0][0]
    assert isinstance(first_add, Organization)
    assert first_add.name == "Default Organization"

    # Second add should be an OrgMembership
    second_add = mock_db.add.call_args_list[1][0][0]
    assert isinstance(second_add, OrgMembership)
    assert second_add.user_id == owner_id
    assert second_add.org_role == "ORG_OWNER"


async def test_skips_if_membership_exists():
    """If user already has an org, don't create another."""
    existing_membership = MagicMock(spec=OrgMembership)
    existing_membership.org_id = uuid.uuid4()

    existing_org = MagicMock(spec=Organization)
    existing_org.id = existing_membership.org_id

    # First execute returns existing membership
    # Second execute returns the org
    mock_result_membership = MagicMock()
    mock_result_membership.scalar_one_or_none.return_value = existing_membership

    mock_result_org = MagicMock()
    mock_result_org.scalar_one_or_none.return_value = existing_org

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute.side_effect = [mock_result_membership, mock_result_org]

    owner_id = uuid.uuid4()
    result = await create_default_org(db=mock_db, owner_id=owner_id)

    # Should NOT have created anything new
    mock_db.add.assert_not_called()
    assert result == existing_org


async def test_org_name_is_default():
    """The auto-created org should be named 'Default Organization'."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute.return_value = mock_result

    await create_default_org(db=mock_db, owner_id=uuid.uuid4())

    org = mock_db.add.call_args_list[0][0][0]
    assert org.name == "Default Organization"


async def test_membership_role_is_org_owner():
    """The bootstrap admin's membership should be ORG_OWNER."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute.return_value = mock_result

    owner_id = uuid.uuid4()
    await create_default_org(db=mock_db, owner_id=owner_id)

    membership = mock_db.add.call_args_list[1][0][0]
    assert membership.org_role == "ORG_OWNER"
    assert membership.user_id == owner_id
