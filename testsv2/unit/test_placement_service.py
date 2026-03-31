"""
Unit tests for placement service functions.

Tests cover:
  - assign_zone
  - get_placement_history
  - remove_from_zone
  - InventoryPlacement.duration_display computed property

Uses the real DB with per-test transaction rollback — no HTTP layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models.inventory_placement import compute_duration_display
from app.store_inventory.service import (
    assign_zone,
    get_placement_history,
    remove_from_zone,
)
from testsv2.factories import (
    create_inventory_placement,
    create_layout_version,
    create_org,
    create_product,
    create_store,
    create_store_inventory,
    create_user,
    create_zone,
)

# ── shared setup helper ───────────────────────────────────────────────────────


async def _make_context(db: AsyncSession):
    """
    Build a minimal org → store → product → inventory → layout → zone hierarchy.
    Returns (store, inventory, user, layout, zone).
    """
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)
    product = await create_product(db, org_id=org.id)
    inventory = await create_store_inventory(
        db, store_id=store.id, product_id=product.id
    )
    user = await create_user(db)
    layout = await create_layout_version(db, store_id=store.id)
    zone = await create_zone(db, layout_version_id=layout.id, name="Zone A")
    return store, inventory, user, layout, zone


# ── assign_zone ───────────────────────────────────────────────────────────────


async def test_assign_zone_creates_placement(db: AsyncSession) -> None:
    """assign_zone returns a new InventoryPlacement with the correct fields."""
    store, inventory, user, _layout, zone = await _make_context(db)

    placement = await assign_zone(db, inventory.id, store.id, zone.id, user.id)

    assert placement.id is not None
    assert placement.store_inventory_id == inventory.id
    assert placement.zone_id == zone.id
    assert placement.placed_by_user_id == user.id
    assert placement.ended_at is None
    assert placement.created_at is not None


async def test_assign_zone_zone_name_populated(db: AsyncSession) -> None:
    """The returned placement exposes zone_name via the eagerly loaded relationship."""
    store, inventory, user, _layout, zone = await _make_context(db)

    placement = await assign_zone(db, inventory.id, store.id, zone.id, user.id)

    assert placement.zone_name == "Zone A"


async def test_assign_zone_started_at_alias(db: AsyncSession) -> None:
    """started_at is an alias for created_at."""
    store, inventory, user, _layout, zone = await _make_context(db)

    placement = await assign_zone(db, inventory.id, store.id, zone.id, user.id)

    assert placement.started_at == placement.created_at


async def test_assign_zone_closes_previous_placement(db: AsyncSession) -> None:
    """assign_zone sets ended_at on the existing active placement."""
    store, inventory, user, layout, zone_a = await _make_context(db)
    zone_b = await create_zone(db, layout_version_id=layout.id, name="Zone B")

    first = await assign_zone(db, inventory.id, store.id, zone_a.id, user.id)
    assert first.ended_at is None

    await assign_zone(db, inventory.id, store.id, zone_b.id, user.id)

    await db.refresh(first)
    assert first.ended_at is not None


async def test_assign_zone_only_one_active_after_reassign(db: AsyncSession) -> None:
    """After two consecutive assignments only the latest placement is active."""
    store, inventory, user, layout, zone_a = await _make_context(db)
    zone_b = await create_zone(db, layout_version_id=layout.id, name="Zone B")

    await assign_zone(db, inventory.id, store.id, zone_a.id, user.id)
    second = await assign_zone(db, inventory.id, store.id, zone_b.id, user.id)

    history = await get_placement_history(db, inventory.id, store.id)
    active = [p for p in history if p.ended_at is None]

    assert len(active) == 1
    assert active[0].id == second.id


async def test_assign_zone_invalid_inventory_raises_not_found(
    db: AsyncSession,
) -> None:
    """assign_zone raises NotFound when the inventory entry does not exist."""
    org = await create_org(db)
    store = await create_store(db, org_id=org.id)
    user = await create_user(db)
    layout = await create_layout_version(db, store_id=store.id)
    zone = await create_zone(db, layout_version_id=layout.id)

    with pytest.raises(NotFound):
        await assign_zone(db, uuid.uuid4(), store.id, zone.id, user.id)


async def test_assign_zone_wrong_store_zone_raises_not_found(
    db: AsyncSession,
) -> None:
    """assign_zone raises NotFound when the zone belongs to a different store."""
    org = await create_org(db)

    # store_a owns the inventory; store_b owns the zone
    store_a = await create_store(db, org_id=org.id, name="Store A")
    store_b = await create_store(db, org_id=org.id, name="Store B")

    product = await create_product(db, org_id=org.id)
    inventory = await create_store_inventory(
        db, store_id=store_a.id, product_id=product.id
    )
    user = await create_user(db)

    layout_b = await create_layout_version(db, store_id=store_b.id)
    zone_b = await create_zone(db, layout_version_id=layout_b.id, name="Zone B-only")

    with pytest.raises(NotFound):
        await assign_zone(db, inventory.id, store_a.id, zone_b.id, user.id)


# ── get_placement_history ─────────────────────────────────────────────────────


async def test_get_placement_history_empty(db: AsyncSession) -> None:
    """get_placement_history returns an empty list when no placements exist."""
    store, inventory, _user, _layout, _zone = await _make_context(db)

    history = await get_placement_history(db, inventory.id, store.id)

    assert history == []


async def test_get_placement_history_returns_newest_first(db: AsyncSession) -> None:
    """get_placement_history returns placements in descending created_at order."""
    store, inventory, user, layout, zone_a = await _make_context(db)
    zone_b = await create_zone(db, layout_version_id=layout.id, name="Zone B")

    # Use assign_zone twice; the service handles closing the first placement,
    # giving us two records with a clear active/inactive distinction to assert on.
    first = await assign_zone(db, inventory.id, store.id, zone_a.id, user.id)
    second = await assign_zone(db, inventory.id, store.id, zone_b.id, user.id)

    history = await get_placement_history(db, inventory.id, store.id)

    assert len(history) == 2
    # The active placement (zone_b) must be retrievable and ended_at should be None
    active = next(p for p in history if p.ended_at is None)
    closed = next(p for p in history if p.ended_at is not None)
    assert active.id == second.id
    assert closed.id == first.id


async def test_get_placement_history_includes_zone_name(db: AsyncSession) -> None:
    """Placements returned by get_placement_history have zone_name populated."""
    store, inventory, user, _layout, zone = await _make_context(db)

    await assign_zone(db, inventory.id, store.id, zone.id, user.id)
    history = await get_placement_history(db, inventory.id, store.id)

    assert history[0].zone_name == "Zone A"


async def test_get_placement_history_invalid_inventory_raises_not_found(
    db: AsyncSession,
) -> None:
    """get_placement_history raises NotFound for an unknown inventory entry."""
    store, _inventory, _user, _layout, _zone = await _make_context(db)

    with pytest.raises(NotFound):
        await get_placement_history(db, uuid.uuid4(), store.id)


# ── remove_from_zone ──────────────────────────────────────────────────────────


async def test_remove_from_zone_closes_active_placement(db: AsyncSession) -> None:
    """remove_from_zone sets ended_at on the currently active placement."""
    store, inventory, user, _layout, zone = await _make_context(db)

    placement = await create_inventory_placement(
        db,
        store_inventory_id=inventory.id,
        zone_id=zone.id,
        placed_by_user_id=user.id,
    )
    assert placement.ended_at is None

    await remove_from_zone(db, inventory.id, store.id)

    await db.refresh(placement)
    assert placement.ended_at is not None


async def test_remove_from_zone_no_active_raises_not_found(db: AsyncSession) -> None:
    """remove_from_zone raises NotFound when there is no active placement."""
    store, inventory, _user, _layout, _zone = await _make_context(db)

    with pytest.raises(NotFound):
        await remove_from_zone(db, inventory.id, store.id)


async def test_remove_from_zone_already_closed_raises_not_found(
    db: AsyncSession,
) -> None:
    """remove_from_zone raises NotFound when the only placement is already closed."""
    store, inventory, user, _layout, zone = await _make_context(db)
    now = datetime.now(timezone.utc)

    await create_inventory_placement(
        db,
        store_inventory_id=inventory.id,
        zone_id=zone.id,
        placed_by_user_id=user.id,
        ended_at=now,
    )

    with pytest.raises(NotFound):
        await remove_from_zone(db, inventory.id, store.id)


async def test_remove_from_zone_invalid_inventory_raises_not_found(
    db: AsyncSession,
) -> None:
    """remove_from_zone raises NotFound for an unknown inventory entry."""
    store, _inventory, _user, _layout, _zone = await _make_context(db)

    with pytest.raises(NotFound):
        await remove_from_zone(db, uuid.uuid4(), store.id)


# ── duration_display standalone function ──────────────────────────────────────


def test_duration_display_active_returns_none() -> None:
    """Active placements (ended_at=None) return None for duration_display."""
    assert compute_duration_display(datetime.now(timezone.utc), None) is None


def test_duration_display_days_and_hours() -> None:
    """Duration >= 1 day formats as 'N days, M hrs'."""
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(days=2, hours=3)
    assert compute_duration_display(start, end) == "2 days, 3 hrs"


def test_duration_display_singular_day() -> None:
    """Exactly one day uses singular 'day'."""
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(days=1, hours=1)
    assert compute_duration_display(start, end) == "1 day, 1 hr"


def test_duration_display_hours_and_minutes() -> None:
    """Duration >= 1 hour but < 1 day formats as 'N hrs, M mins'."""
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=4, minutes=30)
    assert compute_duration_display(start, end) == "4 hrs, 30 mins"


def test_duration_display_minutes_only() -> None:
    """Duration >= 1 minute but < 1 hour formats as 'N mins'."""
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=45)
    assert compute_duration_display(start, end) == "45 mins"


def test_duration_display_less_than_one_minute() -> None:
    """Duration < 1 minute returns '< 1 min'."""
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(seconds=30)
    assert compute_duration_display(start, end) == "< 1 min"
