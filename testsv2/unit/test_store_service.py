"""
Unit tests for app.stores.service using the real DB
with per-test transaction rollback (no HTTP layer).
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.stores.service import create_store, get_by_id, list_stores
from testsv2.factories import create_org


async def test_create_store(db: AsyncSession) -> None:
    """create_store returns a persisted Store with correct fields."""
    org = await create_org(db)

    store = await create_store(db, org.id, "Test Store")

    assert store.id is not None
    assert store.org_id == org.id
    assert store.name == "Test Store"
    assert store.is_active is True
    assert store.created_at is not None
    assert store.updated_at is not None


async def test_list_stores_returns_all_for_org(db: AsyncSession) -> None:
    """list_stores returns every store belonging to the given org."""
    org = await create_org(db)
    other_org = await create_org(db, name="Other Org")

    await create_store(db, org.id, "Alpha")
    await create_store(db, org.id, "Beta")
    await create_store(db, other_org.id, "Should Not Appear")

    stores = await list_stores(db, org.id)

    assert len(stores) == 2
    names = {s.name for s in stores}
    assert names == {"Alpha", "Beta"}


async def test_list_stores_ordered_by_name(db: AsyncSession) -> None:
    """list_stores returns stores sorted alphabetically."""
    org = await create_org(db)

    await create_store(db, org.id, "Zed")
    await create_store(db, org.id, "Apple")
    await create_store(db, org.id, "Mango")

    stores = await list_stores(db, org.id)

    assert [s.name for s in stores] == ["Apple", "Mango", "Zed"]


async def test_list_stores_empty(db: AsyncSession) -> None:
    """list_stores returns an empty list when the org has no stores."""
    org = await create_org(db)

    stores = await list_stores(db, org.id)

    assert stores == []


async def test_get_by_id_success(db: AsyncSession) -> None:
    """get_by_id returns the correct store when org matches."""
    org = await create_org(db)
    store = await create_store(db, org.id, "Target Store")

    retrieved = await get_by_id(db, store.id, org.id)

    assert retrieved.id == store.id
    assert retrieved.name == "Target Store"


async def test_get_by_id_wrong_org_raises_not_found(db: AsyncSession) -> None:
    """get_by_id raises NotFound when the store belongs to a different org."""
    org = await create_org(db)
    store = await create_store(db, org.id, "Target Store")

    with pytest.raises(NotFound):
        await get_by_id(db, store.id, uuid.uuid4())


async def test_get_by_id_unknown_id_raises_not_found(db: AsyncSession) -> None:
    """get_by_id raises NotFound for a completely unknown store ID."""
    org = await create_org(db)

    with pytest.raises(NotFound):
        await get_by_id(db, uuid.uuid4(), org.id)
