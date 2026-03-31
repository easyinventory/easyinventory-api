"""
Functional tests for the zone routes.

  POST   /api/stores/{store_id}/layouts/{layout_version_id}/zones
  GET    /api/stores/{store_id}/layouts/{layout_version_id}/zones
  GET    /api/stores/{store_id}/layouts/{layout_version_id}/zones/{zone_id}
  PUT    /api/stores/{store_id}/layouts/{layout_version_id}/zones/{zone_id}
  DELETE /api/stores/{store_id}/layouts/{layout_version_id}/zones/{zone_id}
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import OrgRole
from app.models.user import User
from testsv2.factories import (
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


def _zones_url(store_id, layout_version_id) -> str:
    return f"/api/stores/{store_id}/layouts/{layout_version_id}/zones"


def _zone_url(store_id, layout_version_id, zone_id) -> str:
    return f"/api/stores/{store_id}/layouts/{layout_version_id}/zones/{zone_id}"


# ── POST – create zone ────────────────────────────────────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_create_zone_returns_201(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Owner can create a zone; response is 201 with correct payload."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(
        db, store_id=store.id, rows=5, cols=5, version_number=1
    )

    response = await client.post(
        _zones_url(store.id, layout.id),
        json={"name": "Zone A", "color": "#FF0000", "cells": [{"row": 0, "col": 0}]},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Zone A"
    assert body["color"] == "#FF0000"
    assert body["cells"] == [{"row": 0, "col": 0}]
    assert body["layout_version_id"] == str(layout.id)


@pytest.mark.usefixtures("bypass_auth")
async def test_create_zone_rejects_cell_outside_grid_bounds(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """A cell outside the grid dimensions returns 400."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(
        db, store_id=store.id, rows=3, cols=3, version_number=1
    )

    response = await client.post(
        _zones_url(store.id, layout.id),
        json={"name": "OOB Zone", "color": "#0000FF", "cells": [{"row": 3, "col": 0}]},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 400


@pytest.mark.usefixtures("bypass_auth")
async def test_create_zone_rejects_cell_col_outside_bounds(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """A cell with col >= layout.cols returns 400."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(
        db, store_id=store.id, rows=3, cols=3, version_number=1
    )

    response = await client.post(
        _zones_url(store.id, layout.id),
        json={"name": "OOB Zone", "color": "#0000FF", "cells": [{"row": 0, "col": 3}]},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 400


@pytest.mark.usefixtures("bypass_auth")
async def test_create_zone_rejects_overlapping_cells(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Creating a zone with cells occupied by another zone returns 409."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(
        db, store_id=store.id, rows=5, cols=5, version_number=1
    )
    await create_zone(
        db,
        layout_version_id=layout.id,
        name="Zone A",
        color="#FF0000",
        cells=[{"row": 0, "col": 0}, {"row": 0, "col": 1}],
    )

    response = await client.post(
        _zones_url(store.id, layout.id),
        json={
            "name": "Zone B",
            "color": "#00FF00",
            "cells": [{"row": 0, "col": 0}],
        },
        headers=_org_headers(org.id),
    )

    assert response.status_code == 409


@pytest.mark.usefixtures("bypass_auth")
async def test_create_zone_rejects_duplicate_cells_in_request(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Providing duplicate cells within the same request body returns 422."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(
        db, store_id=store.id, rows=5, cols=5, version_number=1
    )

    response = await client.post(
        _zones_url(store.id, layout.id),
        json={
            "name": "Zone A",
            "color": "#FF0000",
            "cells": [{"row": 0, "col": 0}, {"row": 0, "col": 0}],
        },
        headers=_org_headers(org.id),
    )

    assert response.status_code == 422


@pytest.mark.usefixtures("bypass_auth")
async def test_create_zone_rejects_zero_cells(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Providing an empty cells list returns 422."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(
        db, store_id=store.id, rows=5, cols=5, version_number=1
    )

    response = await client.post(
        _zones_url(store.id, layout.id),
        json={"name": "Zone A", "color": "#FF0000", "cells": []},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 422


@pytest.mark.usefixtures("bypass_auth")
async def test_create_zone_viewer_forbidden(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """A user with EMPLOYEE role cannot create zones (403)."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.EMPLOYEE
    )
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(
        db, store_id=store.id, rows=5, cols=5, version_number=1
    )

    response = await client.post(
        _zones_url(store.id, layout.id),
        json={"name": "Zone A", "color": "#FF0000", "cells": [{"row": 0, "col": 0}]},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 403


# ── GET – list zones ──────────────────────────────────────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_list_zones_returns_ordered_by_created_at(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """List returns all zones; same-transaction rows share created_at so we verify set membership."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(
        db, store_id=store.id, rows=5, cols=5, version_number=1
    )
    await create_zone(
        db,
        layout_version_id=layout.id,
        name="Zone A",
        color="#FF0000",
        cells=[{"row": 0, "col": 0}],
    )
    await create_zone(
        db,
        layout_version_id=layout.id,
        name="Zone B",
        color="#00FF00",
        cells=[{"row": 1, "col": 0}],
    )

    response = await client.get(
        _zones_url(store.id, layout.id),
        headers=_org_headers(org.id),
    )

    assert response.status_code == 200
    names = [z["name"] for z in response.json()]
    assert set(names) == {"Zone A", "Zone B"}


@pytest.mark.usefixtures("bypass_auth")
async def test_list_zones_empty_returns_empty_list(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """List returns an empty array when no zones exist."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(
        db, store_id=store.id, rows=5, cols=5, version_number=1
    )

    response = await client.get(
        _zones_url(store.id, layout.id),
        headers=_org_headers(org.id),
    )

    assert response.status_code == 200
    assert response.json() == []


# ── GET – single zone ─────────────────────────────────────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_get_zone_returns_200(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """GET /{zone_id} returns the zone."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(
        db, store_id=store.id, rows=5, cols=5, version_number=1
    )
    zone = await create_zone(
        db, layout_version_id=layout.id, name="Zone A", color="#FF0000"
    )

    response = await client.get(
        _zone_url(store.id, layout.id, zone.id),
        headers=_org_headers(org.id),
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(zone.id)


@pytest.mark.usefixtures("bypass_auth")
async def test_get_zone_returns_404_for_unknown(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """GET with unknown zone_id returns 404."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(
        db, store_id=store.id, rows=5, cols=5, version_number=1
    )

    response = await client.get(
        _zone_url(store.id, layout.id, uuid.uuid4()),
        headers=_org_headers(org.id),
    )

    assert response.status_code == 404


# ── PUT – update zone ─────────────────────────────────────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_update_zone_name_and_color(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """PUT updates name and color; cells unchanged."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(
        db, store_id=store.id, rows=5, cols=5, version_number=1
    )
    zone = await create_zone(
        db, layout_version_id=layout.id, name="Zone A", color="#FF0000"
    )

    response = await client.put(
        _zone_url(store.id, layout.id, zone.id),
        json={"name": "Updated Zone", "color": "#0000FF"},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Updated Zone"
    assert body["color"] == "#0000FF"


@pytest.mark.usefixtures("bypass_auth")
async def test_update_zone_cells(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """PUT updates cells when provided."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(
        db, store_id=store.id, rows=5, cols=5, version_number=1
    )
    zone = await create_zone(
        db,
        layout_version_id=layout.id,
        name="Zone A",
        color="#FF0000",
        cells=[{"row": 0, "col": 0}],
    )

    response = await client.put(
        _zone_url(store.id, layout.id, zone.id),
        json={"cells": [{"row": 2, "col": 2}, {"row": 2, "col": 3}]},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 200
    assert response.json()["cells"] == [{"row": 2, "col": 2}, {"row": 2, "col": 3}]


@pytest.mark.usefixtures("bypass_auth")
async def test_update_zone_cells_overlap_rejected(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Updating cells to overlap another zone returns 409."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(
        db, store_id=store.id, rows=5, cols=5, version_number=1
    )
    await create_zone(
        db,
        layout_version_id=layout.id,
        name="Zone A",
        color="#FF0000",
        cells=[{"row": 0, "col": 0}],
    )
    zone_b = await create_zone(
        db,
        layout_version_id=layout.id,
        name="Zone B",
        color="#00FF00",
        cells=[{"row": 1, "col": 0}],
    )

    response = await client.put(
        _zone_url(store.id, layout.id, zone_b.id),
        json={"cells": [{"row": 0, "col": 0}]},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 409


# ── DELETE ────────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_delete_zone_returns_204(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """DELETE returns 204 and the zone is no longer retrievable."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(
        db, store_id=store.id, rows=5, cols=5, version_number=1
    )
    zone = await create_zone(
        db, layout_version_id=layout.id, name="Zone A", color="#FF0000"
    )

    response = await client.delete(
        _zone_url(store.id, layout.id, zone.id),
        headers=_org_headers(org.id),
    )

    assert response.status_code == 204

    # Confirm it is gone
    get_response = await client.get(
        _zone_url(store.id, layout.id, zone.id),
        headers=_org_headers(org.id),
    )
    assert get_response.status_code == 404


@pytest.mark.usefixtures("bypass_auth")
async def test_delete_zone_unknown_returns_404(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """DELETE with an unknown zone_id returns 404."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(
        db, store_id=store.id, rows=5, cols=5, version_number=1
    )

    response = await client.delete(
        _zone_url(store.id, layout.id, uuid.uuid4()),
        headers=_org_headers(org.id),
    )

    assert response.status_code == 404


# ── Zones appear in GET /layouts/active ───────────────────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_zones_visible_in_active_layout(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Zones created in the active layout are included in GET /active."""
    org = await create_org(db)
    await create_membership(
        db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER
    )
    store = await create_store(db, org_id=org.id)
    layout = await create_layout_version(
        db, store_id=store.id, rows=5, cols=5, version_number=1, is_active=True
    )
    await create_zone(
        db,
        layout_version_id=layout.id,
        name="Zone A",
        color="#FF0000",
        cells=[{"row": 0, "col": 0}],
    )

    response = await client.get(
        f"/api/stores/{store.id}/layouts/active",
        headers=_org_headers(org.id),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["zones"]) == 1
    assert body["zones"][0]["name"] == "Zone A"
