"""
Factory functions that INSERT real rows via the test session.

Every factory accepts a ``db`` session (the transaction-rollback fixture)
and returns the persisted SQLAlchemy model instance.  Optional keyword
arguments let individual tests customise only the fields they care about.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import OrgRole, SystemRole
from app.models.organization import Organization
from app.models.org_membership import OrgMembership
from app.models.product import Product
from app.models.product_supplier import ProductSupplier
from app.models.supplier import Supplier
from app.models.user import User


async def create_user(
    db: AsyncSession,
    *,
    email: str = "testuser@example.com",
    cognito_sub: str | None = None,
    system_role: str = SystemRole.USER,
    is_active: bool = True,
) -> User:
    """Insert a ``User`` row and return it."""
    user = User(
        cognito_sub=cognito_sub or str(uuid.uuid4()),
        email=email,
        system_role=system_role,
        is_active=is_active,
    )
    db.add(user)
    await db.flush()
    return user


async def create_org(
    db: AsyncSession,
    *,
    name: str = "Test Organization",
) -> Organization:
    """Insert an ``Organization`` row and return it."""
    org = Organization(name=name)
    db.add(org)
    await db.flush()
    return org


async def create_membership(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    org_role: str = OrgRole.EMPLOYEE,
    is_active: bool = True,
) -> OrgMembership:
    """Insert an ``OrgMembership`` row and return it."""
    membership = OrgMembership(
        org_id=org_id,
        user_id=user_id,
        org_role=org_role,
        is_active=is_active,
    )
    db.add(membership)
    await db.flush()
    return membership


async def create_org_with_owner(
    db: AsyncSession,
    *,
    org_name: str = "Test Organization",
    owner_email: str = "owner@example.com",
    owner_cognito_sub: str | None = None,
    owner_system_role: str = SystemRole.USER,
) -> tuple[Organization, User, OrgMembership]:
    """
    Convenience helper: create an org, a user, and an OWNER membership.

    Returns ``(org, owner_user, membership)``.
    """
    org = await create_org(db, name=org_name)
    owner = await create_user(
        db,
        email=owner_email,
        cognito_sub=owner_cognito_sub,
        system_role=owner_system_role,
    )
    membership = await create_membership(
        db, org_id=org.id, user_id=owner.id, org_role=OrgRole.OWNER
    )
    return org, owner, membership


async def create_supplier(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    name: str = "Test Supplier",
    contact_name: str | None = "Jane Doe",
    contact_email: str | None = "supplier@example.com",
    contact_phone: str | None = None,
    notes: str | None = None,
) -> Supplier:
    """Insert a ``Supplier`` row and return it."""
    supplier = Supplier(
        org_id=org_id,
        name=name,
        contact_name=contact_name,
        contact_email=contact_email,
        contact_phone=contact_phone,
        notes=notes,
    )
    db.add(supplier)
    await db.flush()
    return supplier


async def create_product(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    name: str = "Test Product",
    description: str | None = None,
    sku: str | None = None,
    category: str | None = None,
) -> Product:
    """Insert a ``Product`` row and return it."""
    product = Product(
        org_id=org_id,
        name=name,
        description=description,
        sku=sku,
        category=category,
    )
    db.add(product)
    await db.flush()
    return product


async def create_product_supplier(
    db: AsyncSession,
    *,
    product_id: uuid.UUID,
    supplier_id: uuid.UUID,
    is_active: bool = True,
) -> ProductSupplier:
    """Insert a ``ProductSupplier`` row and return it."""
    link = ProductSupplier(
        product_id=product_id,
        supplier_id=supplier_id,
        is_active=is_active,
    )
    db.add(link)
    await db.flush()
    return link
