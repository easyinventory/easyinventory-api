"""Tests for app.services.invite_service — shared invite orchestration."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import AlreadyExists
from app.core.roles import OrgRole
from app.models.org_membership import OrgMembership
from app.models.user import User
from app.services.invite_service import invite_user_to_org


def _mock_db():
    return AsyncMock()


def _mock_user(email="test@test.com"):
    mock = MagicMock(spec=User)
    mock.id = uuid.uuid4()
    mock.email = email
    return mock


def _mock_membership(is_active=True):
    mock = MagicMock(spec=OrgMembership)
    mock.id = uuid.uuid4()
    mock.is_active = is_active
    return mock


# ── Case 1: Existing user, not a member ──


@patch("app.services.invite_service.org_service")
@patch("app.services.invite_service.user_service")
async def test_existing_user_gets_active_membership(mock_user_svc, mock_org_svc):
    """Known user who isn't a member → active membership, no Cognito call."""
    user = _mock_user()
    new_membership = _mock_membership()

    mock_user_svc.find_user_by_email = AsyncMock(return_value=user)
    mock_org_svc.find_existing_membership = AsyncMock(return_value=None)
    mock_org_svc.create_membership = AsyncMock(return_value=new_membership)

    db = _mock_db()
    org_id = uuid.uuid4()

    result = await invite_user_to_org(
        db=db,
        org_id=org_id,
        email="test@test.com",
        org_role=OrgRole.EMPLOYEE,
    )

    assert result == new_membership
    mock_org_svc.create_membership.assert_called_once_with(
        db=db,
        org_id=org_id,
        user_id=user.id,
        org_role=OrgRole.EMPLOYEE,
        is_active=True,
    )


# ── Case 2: Existing user, already a member ──


@patch("app.services.invite_service.org_service")
@patch("app.services.invite_service.user_service")
async def test_active_member_raises_already_exists(mock_user_svc, mock_org_svc):
    """User who is already an active member → AlreadyExists."""
    user = _mock_user()
    existing = _mock_membership(is_active=True)

    mock_user_svc.find_user_by_email = AsyncMock(return_value=user)
    mock_org_svc.find_existing_membership = AsyncMock(return_value=existing)

    with pytest.raises(AlreadyExists, match="already a member"):
        await invite_user_to_org(
            db=_mock_db(),
            org_id=uuid.uuid4(),
            email="test@test.com",
            org_role=OrgRole.EMPLOYEE,
        )


@patch("app.services.invite_service.org_service")
@patch("app.services.invite_service.user_service")
async def test_pending_invite_raises_already_exists(mock_user_svc, mock_org_svc):
    """User with a pending (inactive) invite → AlreadyExists."""
    user = _mock_user()
    pending = _mock_membership(is_active=False)

    mock_user_svc.find_user_by_email = AsyncMock(return_value=user)
    mock_org_svc.find_existing_membership = AsyncMock(return_value=pending)

    with pytest.raises(AlreadyExists, match="already been invited"):
        await invite_user_to_org(
            db=_mock_db(),
            org_id=uuid.uuid4(),
            email="test@test.com",
            org_role=OrgRole.EMPLOYEE,
        )


# ── Case 3: Unknown email ──


@patch("app.services.invite_service.invite_cognito_user")
@patch("app.services.invite_service.org_service")
@patch("app.services.invite_service.user_service")
async def test_unknown_email_creates_cognito_and_placeholder(
    mock_user_svc, mock_org_svc, mock_cognito
):
    """Unknown email → Cognito invite + placeholder user + inactive membership."""
    placeholder = _mock_user(email="new@test.com")
    new_membership = _mock_membership(is_active=False)

    mock_user_svc.find_user_by_email = AsyncMock(return_value=None)
    mock_user_svc.create_placeholder_user = AsyncMock(return_value=placeholder)
    mock_org_svc.create_membership = AsyncMock(return_value=new_membership)

    db = _mock_db()
    org_id = uuid.uuid4()

    result = await invite_user_to_org(
        db=db,
        org_id=org_id,
        email="new@test.com",
        org_role=OrgRole.ADMIN,
    )

    assert result == new_membership
    mock_cognito.assert_called_once_with("new@test.com")
    mock_user_svc.create_placeholder_user.assert_called_once_with(db, "new@test.com")
    mock_org_svc.create_membership.assert_called_once_with(
        db=db,
        org_id=org_id,
        user_id=placeholder.id,
        org_role=OrgRole.ADMIN,
        is_active=False,
    )


# ── is_new_org flag ──


@patch("app.services.invite_service.org_service")
@patch("app.services.invite_service.user_service")
async def test_is_new_org_skips_duplicate_check(mock_user_svc, mock_org_svc):
    """When is_new_org=True, don't bother checking for existing membership."""
    user = _mock_user()
    new_membership = _mock_membership()

    mock_user_svc.find_user_by_email = AsyncMock(return_value=user)
    mock_org_svc.create_membership = AsyncMock(return_value=new_membership)

    await invite_user_to_org(
        db=_mock_db(),
        org_id=uuid.uuid4(),
        email="test@test.com",
        org_role=OrgRole.OWNER,
        is_new_org=True,
    )

    # find_existing_membership should NOT have been called
    mock_org_svc.find_existing_membership.assert_not_called()
    mock_org_svc.create_membership.assert_called_once()
