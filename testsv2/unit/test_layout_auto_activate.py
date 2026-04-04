"""
Unit tests for layout version auto-activation on first creation.

The ``create_layout_version`` service function should automatically set
``is_active=True`` when the layout is the first one for a store, and
``is_active=False`` for subsequent layouts.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.layouts.service import create_layout_version
from testsv2.factories import (
    create_org,
    create_store,
)


async def test_first_layout_is_auto_activated(db: AsyncSession) -> None:
    """The first layout created for a store is automatically activated."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)

    layout = await create_layout_version(db, store_id=store.id, rows=5, cols=5)

    assert layout.is_active is True
    assert layout.version_number == 1


async def test_second_layout_is_not_auto_activated(db: AsyncSession) -> None:
    """Subsequent layouts are created inactive."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)

    v1 = await create_layout_version(db, store_id=store.id, rows=5, cols=5)
    v2 = await create_layout_version(db, store_id=store.id, rows=6, cols=6)

    assert v1.is_active is True
    assert v2.is_active is False
    assert v2.version_number == 2


async def test_auto_activation_is_per_store(db: AsyncSession) -> None:
    """Each store independently auto-activates its first layout."""
    org = await create_org(db)
    store_a = await create_store(db, org_id=org.id, name="Store A")
    store_b = await create_store(db, org_id=org.id, name="Store B")

    layout_a = await create_layout_version(db, store_id=store_a.id, rows=4, cols=4)
    layout_b = await create_layout_version(db, store_id=store_b.id, rows=4, cols=4)

    assert layout_a.is_active is True
    assert layout_b.is_active is True
