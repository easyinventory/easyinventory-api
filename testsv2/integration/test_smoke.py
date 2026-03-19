"""
Smoke tests that validate the transaction-per-test rollback fixture
and the factory helpers work end-to-end against a real Postgres database.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.org_membership import OrgMembership
from app.models.product import Product
from app.models.product_supplier import ProductSupplier
from app.models.supplier import Supplier
from app.models.user import User
from testsv2.factories import (
    create_membership,
    create_org,
    create_org_with_owner,
    create_product,
    create_product_supplier,
    create_supplier,
    create_user,
)

# ── Basic factory round-trips ──────────────────────────


async def test_create_user_persists(db: AsyncSession):
    user = await create_user(db, email="alice@example.com")
    assert user.id is not None
    assert user.email == "alice@example.com"

    row = await db.get(User, user.id)
    assert row is not None
    assert row.email == "alice@example.com"


async def test_create_org_persists(db: AsyncSession):
    org = await create_org(db, name="Acme Corp")
    assert org.id is not None

    row = await db.get(Organization, org.id)
    assert row is not None
    assert row.name == "Acme Corp"


async def test_create_membership_links_user_to_org(db: AsyncSession):
    org = await create_org(db)
    user = await create_user(db)
    membership = await create_membership(db, org_id=org.id, user_id=user.id)

    row = await db.get(OrgMembership, membership.id)
    assert row is not None
    assert row.org_id == org.id
    assert row.user_id == user.id


async def test_create_org_with_owner_convenience(db: AsyncSession):
    org, owner, membership = await create_org_with_owner(db, org_name="My Shop")
    assert org.name == "My Shop"
    assert owner.email == "owner@example.com"
    assert membership.org_role == "ORG_OWNER"
    assert membership.org_id == org.id
    assert membership.user_id == owner.id


async def test_create_supplier_persists(db: AsyncSession):
    org = await create_org(db)
    supplier = await create_supplier(db, org_id=org.id, name="FastShip")

    row = await db.get(Supplier, supplier.id)
    assert row is not None
    assert row.name == "FastShip"
    assert row.org_id == org.id


async def test_create_product_persists(db: AsyncSession):
    org = await create_org(db)
    product = await create_product(db, org_id=org.id, name="Widget", sku="W-001")

    row = await db.get(Product, product.id)
    assert row is not None
    assert row.name == "Widget"
    assert row.sku == "W-001"


async def test_create_product_supplier_link(db: AsyncSession):
    org = await create_org(db)
    product = await create_product(db, org_id=org.id)
    supplier = await create_supplier(db, org_id=org.id)
    link = await create_product_supplier(
        db, product_id=product.id, supplier_id=supplier.id
    )

    row = await db.get(ProductSupplier, link.id)
    assert row is not None
    assert row.product_id == product.id
    assert row.supplier_id == supplier.id


# ── Transaction rollback isolation ──────────────────────


async def test_rollback_isolation_a(db: AsyncSession):
    """Create a user with a unique email. Test B must NOT see it."""
    await create_user(db, email="only-in-a@example.com")
    result = await db.execute(select(User).where(User.email == "only-in-a@example.com"))
    assert result.scalar_one_or_none() is not None


async def test_rollback_isolation_b(db: AsyncSession):
    """This runs after test A — the user created there should be gone."""
    result = await db.execute(select(User).where(User.email == "only-in-a@example.com"))
    assert (
        result.scalar_one_or_none() is None
    ), "Transaction rollback failed: test A's data leaked into test B"


# ── Query exercises ────────────────────────────────────


async def test_query_users_by_email(db: AsyncSession):
    await create_user(db, email="findme@example.com")
    await create_user(db, email="other@example.com", cognito_sub=str(uuid.uuid4()))

    result = await db.execute(select(User).where(User.email == "findme@example.com"))
    users = result.scalars().all()
    assert len(users) == 1
    assert users[0].email == "findme@example.com"


async def test_org_membership_relationship_loading(db: AsyncSession):
    """Verify that selectin relationship loading works with real data."""
    org, owner, _ = await create_org_with_owner(db)

    # Refresh to trigger relationship loading
    await db.refresh(org, ["memberships"])
    assert len(org.memberships) == 1
    assert org.memberships[0].user_id == owner.id
