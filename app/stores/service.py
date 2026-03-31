from __future__ import annotations

import uuid

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models.store import Store


async def create_store(db: AsyncSession, org_id: uuid.UUID, name: str) -> Store:
    """Create a new store for an organization."""
    store = Store(org_id=org_id, name=name, is_active=True)
    db.add(store)
    await db.flush()
    await db.refresh(store)
    return store


async def list_stores(db: AsyncSession, org_id: uuid.UUID) -> list[Store]:
    """List all stores for an organization, ordered by name."""
    stmt = select(Store).where(Store.org_id == org_id).order_by(Store.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_by_id(
    db: AsyncSession,
    store_id: uuid.UUID,
    org_id: uuid.UUID,
) -> Store:
    """Get a store by ID, validating organization ownership."""
    stmt = select(Store).where(
        and_(Store.id == store_id, Store.org_id == org_id)
    )
    result = await db.execute(stmt)
    store = result.scalars().first()
    if store is None:
        raise NotFound(f"Store {store_id} not found in organization {org_id}")
    return store
