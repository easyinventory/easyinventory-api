"""
Startup bootstrap seeder.

Runs once during application lifespan to ensure the bootstrap admin
user and default organization exist in the database.  Uses the same
placeholder pattern as the invite flow — the admin record is created
with a ``pending:bootstrap`` cognito_sub and claimed automatically on
first real login via the standard placeholder-claim logic in
user_service.

This replaces the old approach where bootstrap checks were scattered
across user_service and org_service and evaluated on every new-user
login.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.roles import OrgRole, SystemRole
from app.models.organization import Organization
from app.models.org_membership import OrgMembership
from app.models.product import Product
from app.models.product_supplier import ProductSupplier
from app.models.supplier import Supplier
from app.models.user import User

# ── Seed data ──

SEED_SUPPLIERS = [
    {
        "name": "Fresh Farms Co.",
        "contact_name": "Maria Garcia",
        "contact_email": "maria@freshfarms.com",
        "contact_phone": "555-0101",
        "notes": "Local organic produce supplier",
    },
    {
        "name": "Pacific Coast Distributors",
        "contact_name": "James Chen",
        "contact_email": "james@pacificcoast.com",
        "contact_phone": "555-0102",
        "notes": "West coast distribution, 2-day delivery",
    },
    {
        "name": "Valley Grains & Goods",
        "contact_name": "Sarah Miller",
        "contact_email": "sarah@valleygrains.com",
        "contact_phone": "555-0103",
        "notes": "Specialty grains and dry goods",
    },
    {
        "name": "Mountain Spring Dairy",
        "contact_name": "Tom Baker",
        "contact_email": "tom@mountainspring.com",
        "contact_phone": "555-0104",
        "notes": "Dairy and refrigerated products",
    },
]

SEED_PRODUCTS: list[dict[str, Any]] = [
    {
        "name": "Organic Apples",
        "description": "Fresh organic Fuji apples",
        "sku": "PRD-001",
        "category": "Produce",
        "supplier_indices": [0, 1],  # Fresh Farms + Pacific Coast
    },
    {
        "name": "Whole Wheat Flour",
        "description": "Stone-ground whole wheat flour, 25lb bag",
        "sku": "PRD-002",
        "category": "Dry Goods",
        "supplier_indices": [2],  # Valley Grains
    },
    {
        "name": "Organic Oranges",
        "description": "Navel oranges, premium grade",
        "sku": "PRD-003",
        "category": "Produce",
        "supplier_indices": [0, 1],  # Fresh Farms + Pacific Coast
    },
    {
        "name": "Whole Milk",
        "description": "Fresh whole milk, 1 gallon",
        "sku": "PRD-004",
        "category": "Dairy",
        "supplier_indices": [3],  # Mountain Spring
    },
    {
        "name": "Brown Rice",
        "description": "Long grain brown rice, 50lb bag",
        "sku": "PRD-005",
        "category": "Dry Goods",
        "supplier_indices": [2, 1],  # Valley Grains + Pacific Coast
    },
]


async def run_bootstrap(db: AsyncSession) -> None:
    """
    Seed the bootstrap admin + default org if configured.

    Idempotent — safe to call on every startup.

    Handles three scenarios:
      1. User does not exist → create placeholder user, org, and membership.
      2. User exists but has no org membership → create org + membership
         and ensure system_role is SYSTEM_ADMIN.  This covers the case
         where a fresh DB was migrated and the user logged in via Cognito
         before bootstrap could create the org.
      3. User exists and already has a membership → no-op.
    """
    email = (settings.BOOTSTRAP_ADMIN_EMAIL or "").strip().lower()
    if not email:
        print("[bootstrap] No BOOTSTRAP_ADMIN_EMAIL configured — skipping")
        return

    org_name = (settings.BOOTSTRAP_ORG_NAME or "").strip() or "Default Organization"

    # ── Check if user already exists ──
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user is None:
        # ── Scenario 1: brand-new → create placeholder admin ──
        user = User(
            cognito_sub=f"pending:{email}",
            email=email,
            system_role=SystemRole.ADMIN,
            is_active=False,
        )
        db.add(user)
        await db.flush()

        org = Organization(name=org_name)
        db.add(org)
        await db.flush()

        membership = OrgMembership(
            org_id=org.id,
            user_id=user.id,
            org_role=OrgRole.OWNER,
            is_active=False,
        )
        db.add(membership)
        await db.flush()

        print(f"[bootstrap] Created admin placeholder '{email}' + org '{org_name}'")
        await _seed_sample_data(db, org.id)
        return

    # ── User exists — check for org membership ──
    mem_stmt = select(OrgMembership).where(OrgMembership.user_id == existing_user.id)
    mem_result = await db.execute(mem_stmt)
    existing_membership = mem_result.scalar_one_or_none()

    if existing_membership is not None:
        print(f"[bootstrap] Admin user '{email}' already exists")
        await _seed_sample_data(db, existing_membership.org_id)
        return

    # ── Scenario 2: user exists but no org/membership ──
    if existing_user.system_role != SystemRole.ADMIN:
        existing_user.system_role = SystemRole.ADMIN
        print(f"[bootstrap] Promoted '{email}' to {SystemRole.ADMIN}")

    org = Organization(name=org_name)
    db.add(org)
    await db.flush()

    membership = OrgMembership(
        org_id=org.id,
        user_id=existing_user.id,
        org_role=OrgRole.OWNER,
        is_active=True,
    )
    db.add(membership)
    await db.flush()

    print(f"[bootstrap] Created org '{org_name}' + owner membership for '{email}'")
    await _seed_sample_data(db, org.id)


async def _seed_sample_data(db: AsyncSession, org_id: uuid.UUID) -> None:
    """
    Seed sample suppliers, products, and product-supplier links.

    Idempotent — skips if any suppliers already exist for the org.
    """
    count_stmt = (
        select(func.count()).select_from(Supplier).where(Supplier.org_id == org_id)
    )
    result = await db.execute(count_stmt)
    if result.scalar_one() > 0:
        print("[bootstrap] Seed data already exists — skipping")
        return

    # ── Create suppliers ──
    suppliers: list[Supplier] = []
    for data in SEED_SUPPLIERS:
        supplier = Supplier(org_id=org_id, **data)
        db.add(supplier)
        suppliers.append(supplier)
    await db.flush()

    # ── Create products + links ──
    for data in SEED_PRODUCTS:
        product = Product(
            org_id=org_id,
            name=data["name"],
            description=data["description"],
            sku=data["sku"],
            category=data["category"],
        )
        db.add(product)
        await db.flush()

        for idx in data["supplier_indices"]:
            link = ProductSupplier(
                product_id=product.id,
                supplier_id=suppliers[int(idx)].id,
                is_active=True,
            )
            db.add(link)
        await db.flush()

    print(
        f"[bootstrap] Seeded {len(SEED_SUPPLIERS)} suppliers, "
        f"{len(SEED_PRODUCTS)} products"
    )
