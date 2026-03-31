"""
Integration tests for app.bootstrap.seeder using a real DB session.

The seeder's org-creation path now goes through orgs.service.create_organization
which auto-creates a default store, so we verify the full DB state rather than
asserting on mock call-arg positions.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bootstrap.seeder import run_bootstrap
from app.core.roles import OrgRole, SystemRole
from app.models.org_membership import OrgMembership
from app.models.organization import Organization
from app.models.store import Store
from app.models.user import User

# ── Scenario 1: brand-new database ────────────────────────────────────────────


@patch("app.bootstrap.seeder.settings")
async def test_creates_placeholder_user(mock_settings, db: AsyncSession) -> None:
    """Scenario 1: creates a pending SYSTEM_ADMIN user."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = "Test Org"

    await run_bootstrap(db)

    result = await db.execute(select(User).where(User.email == "admin@company.com"))
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.cognito_sub == "pending:admin@company.com"
    assert user.system_role == SystemRole.ADMIN
    assert user.is_active is False


@patch("app.bootstrap.seeder.settings")
async def test_creates_default_org(mock_settings, db: AsyncSession) -> None:
    """Scenario 1: creates an organization with the configured name."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = "My Company"

    await run_bootstrap(db)

    result = await db.execute(
        select(Organization).where(Organization.name == "My Company")
    )
    org = result.scalar_one_or_none()
    assert org is not None


@patch("app.bootstrap.seeder.settings")
async def test_creates_owner_membership(mock_settings, db: AsyncSession) -> None:
    """Scenario 1: owner membership is created and is inactive (placeholder)."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = "Test Org"

    await run_bootstrap(db)

    result = await db.execute(select(OrgMembership))
    membership = result.scalars().first()
    assert membership is not None
    assert membership.org_role == OrgRole.OWNER
    assert membership.is_active is False


@patch("app.bootstrap.seeder.settings")
async def test_membership_inactive_until_login(mock_settings, db: AsyncSession) -> None:
    """Scenario 1: both user and membership are inactive until first real login."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = "Test Org"

    await run_bootstrap(db)

    user_result = await db.execute(
        select(User).where(User.email == "admin@company.com")
    )
    user = user_result.scalar_one_or_none()
    mem_result = await db.execute(select(OrgMembership))
    membership = mem_result.scalars().first()

    assert user is not None and user.is_active is False
    assert membership is not None and membership.is_active is False


@patch("app.bootstrap.seeder.settings")
async def test_auto_creates_default_store(mock_settings, db: AsyncSession) -> None:
    """Scenario 1: create_organization auto-creates a default store."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = "Test Org"

    await run_bootstrap(db)

    result = await db.execute(select(Store))
    stores = result.scalars().all()
    assert len(stores) == 1
    assert stores[0].name == "Test Org Default Store"
    assert stores[0].is_active is True


@patch("app.bootstrap.seeder.settings")
async def test_default_org_name_fallback(mock_settings, db: AsyncSession) -> None:
    """Empty BOOTSTRAP_ORG_NAME falls back to 'Default Organization'."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = ""

    await run_bootstrap(db)

    result = await db.execute(select(Organization))
    org = result.scalars().first()
    assert org is not None
    assert org.name == "Default Organization"


@patch("app.bootstrap.seeder.settings")
async def test_skips_when_email_not_configured(mock_settings, db: AsyncSession) -> None:
    """Empty BOOTSTRAP_ADMIN_EMAIL skips all DB work."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = ""
    mock_settings.BOOTSTRAP_ORG_NAME = "Test Org"

    await run_bootstrap(db)

    result = await db.execute(select(User))
    assert result.scalars().first() is None


@patch("app.bootstrap.seeder.settings")
async def test_email_is_lowercased(mock_settings, db: AsyncSession) -> None:
    """Email is normalized to lowercase."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "  Admin@Company.COM  "
    mock_settings.BOOTSTRAP_ORG_NAME = "Test Org"

    await run_bootstrap(db)

    result = await db.execute(select(User).where(User.email == "admin@company.com"))
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.cognito_sub == "pending:admin@company.com"


# ── Scenario 2: user exists, no membership ────────────────────────────────────


@patch("app.bootstrap.seeder.settings")
async def test_creates_org_when_user_exists_without_membership(
    mock_settings, db: AsyncSession
) -> None:
    """Scenario 2: org + membership created for an existing user with no membership."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = "My Company"

    # Pre-create the user (simulates Cognito login before bootstrap ran)
    user = User(
        cognito_sub="real-cognito-sub",
        email="admin@company.com",
        system_role=SystemRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    await run_bootstrap(db)

    org_result = await db.execute(
        select(Organization).where(Organization.name == "My Company")
    )
    org = org_result.scalar_one_or_none()
    assert org is not None

    mem_result = await db.execute(
        select(OrgMembership).where(OrgMembership.user_id == user.id)
    )
    membership = mem_result.scalars().first()
    assert membership is not None
    assert membership.org_role == OrgRole.OWNER
    assert membership.is_active is True


@patch("app.bootstrap.seeder.settings")
async def test_membership_active_when_user_already_exists(
    mock_settings, db: AsyncSession
) -> None:
    """Scenario 2: membership for an already-real user is immediately active."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = "Test Org"

    user = User(
        cognito_sub="real-sub",
        email="admin@company.com",
        system_role=SystemRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    await run_bootstrap(db)

    mem_result = await db.execute(
        select(OrgMembership).where(OrgMembership.user_id == user.id)
    )
    membership = mem_result.scalars().first()
    assert membership is not None
    assert membership.is_active is True


@patch("app.bootstrap.seeder.settings")
async def test_promotes_existing_user_to_admin(mock_settings, db: AsyncSession) -> None:
    """Scenario 2: non-admin user is promoted to SYSTEM_ADMIN."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = "Test Org"

    user = User(
        cognito_sub="real-sub",
        email="admin@company.com",
        system_role=SystemRole.USER,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    await run_bootstrap(db)

    await db.refresh(user)
    assert user.system_role == SystemRole.ADMIN


# ── Scenario 3: user + membership already exist ───────────────────────────────


@patch("app.bootstrap.seeder.settings")
async def test_skips_when_user_already_has_membership(
    mock_settings, db: AsyncSession
) -> None:
    """Scenario 3: no duplicate org or membership created."""
    mock_settings.BOOTSTRAP_ADMIN_EMAIL = "admin@company.com"
    mock_settings.BOOTSTRAP_ORG_NAME = "Test Org"

    user = User(
        cognito_sub="real-sub",
        email="admin@company.com",
        system_role=SystemRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    org = Organization(name="Existing Org")
    db.add(org)
    await db.flush()

    membership = OrgMembership(
        org_id=org.id, user_id=user.id, org_role=OrgRole.OWNER, is_active=True
    )
    db.add(membership)
    await db.flush()

    org_count_before = len((await db.execute(select(Organization))).scalars().all())

    await run_bootstrap(db)

    org_count_after = len((await db.execute(select(Organization))).scalars().all())
    assert org_count_after == org_count_before
