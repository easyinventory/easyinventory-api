"""
Functional tests for the fixture routes.

  POST   /api/stores/{store_id}/layouts/{layout_version_id}/fixtures
  GET    /api/stores/{store_id}/layouts/{layout_version_id}/fixtures
  GET    /api/stores/{store_id}/layouts/{layout_version_id}/fixtures/{fixture_id}
  PUT    /api/stores/{store_id}/layouts/{layout_version_id}/fixtures/{fixture_id}
  DELETE /api/stores/{store_id}/layouts/{layout_version_id}/fixtures/{fixture_id}
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import OrgRole
from app.models.fixture import FixtureType
from app.models.user import User
from testsv2.factories import (
    create_fixture,
    create_layout_version,
    create_membership,
    create_org,
    create_store,
    create_zone,
)
from testsv2.functional.conftest import AUTH_HEADER

# ── Helpers ───────────────────────────────────────────────────────────────────


def _org_headers(org_id) -> dict:
    return {**AUTH_HEADER, "X-Org-Id": str(org_id)}


def _fixtures_url(store_id, layout_version_id) -> str:
    return f"/api/stores/{store_id}/layouts/{layout_version_id}/fixtures"


def _fixture_url(store_id, layout_version_id, fixture_id) -> str:
    return f"/api/stores/{store_id}/layouts/{layout_version_id}/fixtures/{fixture_id}"


# ── POST – create fixture ─────────────────────────────────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_create_fixture_returns_201(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Owner can create a fixture; response is 201 with correct payload."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(db, store_id=store.id, rows=5, cols=5, version_number=1)

    response = await client.post(
        _fixtures_url(store.id, layout.id),
        json={"fixture_type": "WALL", "cells": [{"row": 0, "col": 0}]},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["fixture_type"] == "WALL"
    assert body["name"] is None
    assert body["cells"] == [{"row": 0, "col": 0}]
    assert body["layout_version_id"] == str(layout.id)


@pytest.mark.usefixtures("bypass_auth")
async def test_create_fixture_with_name_returns_201(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Owner can optionally supply a name."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(db, store_id=store.id, rows=5, cols=5, version_number=1)

    response = await client.post(
        _fixtures_url(store.id, layout.id),
        json={"fixture_type": "CHECKOUT", "name": "Main Checkout", "cells": [{"row": 1, "col": 1}]},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Main Checkout"
    assert response.json()["fixture_type"] == "CHECKOUT"


@pytest.mark.usefixtures("bypass_auth")
async def test_create_fixture_invalid_type_returns_422(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """An invalid fixture_type enum value returns 422."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(db, store_id=store.id, rows=5, cols=5, version_number=1)

    response = await client.post(
        _fixtures_url(store.id, layout.id),
        json={"fixture_type": "NOT_A_TYPE", "cells": [{"row": 0, "col": 0}]},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 422


@pytest.mark.usefixtures("bypass_auth")
async def test_create_fixture_rejects_cell_outside_grid_bounds(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """A cell outside the grid dimensions returns 400."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(db, store_id=store.id, rows=3, cols=3, version_number=1)

    response = await client.post(
        _fixtures_url(store.id, layout.id),
        json={"fixture_type": "WALL", "cells": [{"row": 3, "col": 0}]},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 400


@pytest.mark.usefixtures("bypass_auth")
async def test_create_fixture_overlaps_existing_fixture_returns_409(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Cells overlapping an existing fixture return 409."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(db, store_id=store.id, rows=5, cols=5, version_number=1)
    await create_fixture(db, layout_version_id=layout.id, cells=[{"row": 2, "col": 2}])

    response = await client.post(
        _fixtures_url(store.id, layout.id),
        json={"fixture_type": "DOOR", "cells": [{"row": 2, "col": 2}]},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 409


@pytest.mark.usefixtures("bypass_auth")
async def test_create_fixture_overlaps_existing_zone_returns_409(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Cells overlapping an existing zone return 409."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(db, store_id=store.id, rows=5, cols=5, version_number=1)
    await create_zone(db, layout_version_id=layout.id, cells=[{"row": 1, "col": 1}])

    response = await client.post(
        _fixtures_url(store.id, layout.id),
        json={"fixture_type": "PILLAR", "cells": [{"row": 1, "col": 1}]},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 409


@pytest.mark.usefixtures("bypass_auth")
async def test_create_fixture_duplicate_cells_in_request_returns_422(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Duplicate cells in the same request return 422."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(db, store_id=store.id, rows=5, cols=5, version_number=1)

    response = await client.post(
        _fixtures_url(store.id, layout.id),
        json={"fixture_type": "WALL", "cells": [{"row": 0, "col": 0}, {"row": 0, "col": 0}]},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 422


@pytest.mark.usefixtures("bypass_auth")
async def test_create_fixture_empty_cells_returns_422(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """An empty cells list returns 422."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(db, store_id=store.id, rows=5, cols=5, version_number=1)

    response = await client.post(
        _fixtures_url(store.id, layout.id),
        json={"fixture_type": "WALL", "cells": []},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 422


@pytest.mark.usefixtures("bypass_auth")
async def test_create_fixture_employee_forbidden(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """An EMPLOYEE role cannot create fixtures (403)."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.EMPLOYEE)
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(db, store_id=store.id, rows=5, cols=5, version_number=1)

    response = await client.post(
        _fixtures_url(store.id, layout.id),
        json={"fixture_type": "WALL", "cells": [{"row": 0, "col": 0}]},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 403


# ── GET list ─────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_list_fixtures_returns_all_ordered_by_created_at(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """List endpoint returns fixtures ordered by creation date."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.EMPLOYEE)
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(db, store_id=store.id, rows=5, cols=5, version_number=1)

    f1 = await create_fixture(db, layout_version_id=layout.id, cells=[{"row": 0, "col": 0}])
    f2 = await create_fixture(db, layout_version_id=layout.id, fixture_type=FixtureType.DOOR, cells=[{"row": 1, "col": 1}])

    response = await client.get(
        _fixtures_url(store.id, layout.id),
        headers=_org_headers(org.id),
    )

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert ids == [str(f1.id), str(f2.id)]


@pytest.mark.usefixtures("bypass_auth")
async def test_list_fixtures_empty(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """List endpoint returns an empty list when no fixtures exist."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.EMPLOYEE)
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(db, store_id=store.id, rows=5, cols=5, version_number=1)

    response = await client.get(
        _fixtures_url(store.id, layout.id),
        headers=_org_headers(org.id),
    )

    assert response.status_code == 200
    assert response.json() == []


# ── GET single ───────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_get_fixture_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Any org member can fetch a fixture by ID."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.EMPLOYEE)
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(db, store_id=store.id, rows=5, cols=5, version_number=1)
    fixture = await create_fixture(db, layout_version_id=layout.id, name="North Wall")

    response = await client.get(
        _fixture_url(store.id, layout.id, fixture.id),
        headers=_org_headers(org.id),
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(fixture.id)
    assert response.json()["name"] == "North Wall"


@pytest.mark.usefixtures("bypass_auth")
async def test_get_fixture_unknown_id_returns_404(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Fetching a non-existent fixture ID returns 404."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.EMPLOYEE)
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(db, store_id=store.id, rows=5, cols=5, version_number=1)

    response = await client.get(
        _fixture_url(store.id, layout.id, uuid.uuid4()),
        headers=_org_headers(org.id),
    )

    assert response.status_code == 404


# ── PUT – update fixture ──────────────────────────────────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_update_fixture_type_and_name(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Owner can update fixture_type and name."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(db, store_id=store.id, rows=5, cols=5, version_number=1)
    fixture = await create_fixture(db, layout_version_id=layout.id, cells=[{"row": 0, "col": 0}])

    response = await client.put(
        _fixture_url(store.id, layout.id, fixture.id),
        json={"fixture_type": "CHECKOUT", "name": "Self Checkout"},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 200
    assert response.json()["fixture_type"] == "CHECKOUT"
    assert response.json()["name"] == "Self Checkout"


@pytest.mark.usefixtures("bypass_auth")
async def test_update_fixture_cells(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Owner can replace cells on a fixture."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(db, store_id=store.id, rows=5, cols=5, version_number=1)
    fixture = await create_fixture(db, layout_version_id=layout.id, cells=[{"row": 0, "col": 0}])

    response = await client.put(
        _fixture_url(store.id, layout.id, fixture.id),
        json={"cells": [{"row": 2, "col": 2}]},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 200
    assert response.json()["cells"] == [{"row": 2, "col": 2}]


@pytest.mark.usefixtures("bypass_auth")
async def test_update_fixture_overlap_rejected(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Updating fixture cells to overlap another fixture returns 409."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(db, store_id=store.id, rows=5, cols=5, version_number=1)
    await create_fixture(db, layout_version_id=layout.id, fixture_type=FixtureType.WALL, cells=[{"row": 3, "col": 3}])
    fixture2 = await create_fixture(db, layout_version_id=layout.id, fixture_type=FixtureType.DOOR, cells=[{"row": 4, "col": 4}])

    response = await client.put(
        _fixture_url(store.id, layout.id, fixture2.id),
        json={"cells": [{"row": 3, "col": 3}]},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 409


# ── DELETE ────────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_delete_fixture_returns_204(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Owner can delete a fixture; subsequent GET returns 404."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(db, store_id=store.id, rows=5, cols=5, version_number=1)
    fixture = await create_fixture(db, layout_version_id=layout.id)

    response = await client.delete(
        _fixture_url(store.id, layout.id, fixture.id),
        headers=_org_headers(org.id),
    )

    assert response.status_code == 204

    get_response = await client.get(
        _fixture_url(store.id, layout.id, fixture.id),
        headers=_org_headers(org.id),
    )
    assert get_response.status_code == 404


@pytest.mark.usefixtures("bypass_auth")
async def test_delete_fixture_unknown_id_returns_404(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Deleting a non-existent fixture ID returns 404."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(db, store_id=store.id, rows=5, cols=5, version_number=1)

    response = await client.delete(
        _fixture_url(store.id, layout.id, uuid.uuid4()),
        headers=_org_headers(org.id),
    )

    assert response.status_code == 404


# ── Zone overlap check (BE-08 TODO resolved) ─────────────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_create_zone_overlapping_fixture_returns_409(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Creating a zone whose cells overlap an existing fixture returns 409."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(db, store_id=store.id, rows=5, cols=5, version_number=1)
    await create_fixture(db, layout_version_id=layout.id, cells=[{"row": 2, "col": 2}])

    response = await client.post(
        f"/api/stores/{store.id}/layouts/{layout.id}/zones",
        json={"name": "Conflict Zone", "color": "#00FF00", "cells": [{"row": 2, "col": 2}]},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 409


# ── Integration: fixtures appear in active layout response ────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_fixtures_appear_in_active_layout_response(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Fixtures are included in the GET /layouts/active response payload."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.EMPLOYEE)
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(
        db, store_id=store.id, rows=5, cols=5, version_number=1, is_active=True
    )
    fixture = await create_fixture(
        db, layout_version_id=layout.id, fixture_type=FixtureType.STAIRS, cells=[{"row": 0, "col": 0}]
    )

    response = await client.get(
        f"/api/stores/{store.id}/layouts/active",
        headers=_org_headers(org.id),
    )

    assert response.status_code == 200
    fixture_ids = [f["id"] for f in response.json()["fixtures"]]
    assert str(fixture.id) in fixture_ids
