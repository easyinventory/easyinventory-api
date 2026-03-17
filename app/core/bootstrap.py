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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.roles import OrgRole, SystemRole
from app.models.organization import Organization
from app.models.org_membership import OrgMembership
from app.models.user import User


async def run_bootstrap(db: AsyncSession) -> None:
    """
    Seed the bootstrap admin + default org if configured.

    Idempotent — safe to call on every startup.  Does nothing if:
      - BOOTSTRAP_ADMIN_EMAIL is empty / unset
      - A user with that email already exists (regardless of role)
    """
    email = (settings.BOOTSTRAP_ADMIN_EMAIL or "").strip().lower()
    if not email:
        print("[bootstrap] No BOOTSTRAP_ADMIN_EMAIL configured — skipping")
        return

    # ── Check if user already exists ──
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user is not None:
        print(f"[bootstrap] Admin user '{email}' already exists — skipping")
        return

    # ── Create placeholder admin ──
    user = User(
        cognito_sub=f"pending:{email}",
        email=email,
        system_role=SystemRole.ADMIN,
        is_active=False,
    )
    db.add(user)
    await db.flush()

    # ── Create default org ──
    org_name = (settings.BOOTSTRAP_ORG_NAME or "").strip() or "Default Organization"
    org = Organization(name=org_name)
    db.add(org)
    await db.flush()

    # ── Add admin as org owner ──
    membership = OrgMembership(
        org_id=org.id,
        user_id=user.id,
        org_role=OrgRole.OWNER,
        is_active=False,
    )
    db.add(membership)
    await db.flush()

    print(f"[bootstrap] Created admin placeholder '{email}' + org '{org_name}'")
