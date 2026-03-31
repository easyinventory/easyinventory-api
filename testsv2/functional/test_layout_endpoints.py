"""
Functional tests for the layout version routes.

  POST   /api/stores/{store_id}/layouts
  POST   /api/stores/{store_id}/layouts/{id}/activate
  GET    /api/stores/{store_id}/layouts/active
  GET    /api/stores/{store_id}/layouts
"""

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
)
from testsv2.functional.conftest import AUTH_HEADER

# ── Helpers ───────────────────────────────────────────────────────────────────


def _org_headers(org_id) -> dict:
    """Return auth + X-Org-Id headers for the given org."""
    return {**AUTH_HEADER, "X-Org-Id": str(org_id)}


# ── POST /api/stores/{store_id}/layouts ───────────────────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_create_layout_version_returns_201(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Owner can create a layout version; response is 201 with correct payload."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)
    store = await create_store(db, org_id=org.id)

    response = await client.post(
        f"/api/stores/{store.id}/layouts",
        json={"rows": 10, "cols": 8},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["rows"] == 10
    assert body["cols"] == 8
    assert body["version_number"] == 1
    assert body["is_active"] is False
    assert body["store_id"] == str(store.id)
    assert body["zones"] == []


@pytest.mark.usefixtures("bypass_auth")
async def test_create_layout_version_increments_version_number(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Second version gets version_number 2."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)
    store = await create_store(db, org_id=org.id)

    await client.post(
        f"/api/stores/{store.id}/layouts",
        json={"rows": 5, "cols": 5},
        headers=_org_headers(org.id),
    )
    response = await client.post(
        f"/api/stores/{store.id}/layouts",
        json={"rows": 6, "cols": 6},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 201
    assert response.json()["version_number"] == 2


@pytest.mark.usefixtures("bypass_auth")
async def test_create_layout_version_rejects_rows_below_minimum(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """rows < 2 returns 422 Unprocessable Entity."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)
    store = await create_store(db, org_id=org.id)

    response = await client.post(
        f"/api/stores/{store.id}/layouts",
        json={"rows": 1, "cols": 5},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 422


@pytest.mark.usefixtures("bypass_auth")
async def test_create_layout_version_rejects_cols_above_maximum(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """cols > 30 returns 422 Unprocessable Entity."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)
    store = await create_store(db, org_id=org.id)

    response = await client.post(
        f"/api/stores/{store.id}/layouts",
        json={"rows": 5, "cols": 31},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 422


@pytest.mark.usefixtures("bypass_auth")
async def test_create_layout_version_forbidden_for_viewer(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Viewer role cannot create a layout version; returns 403."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.VIEWER)
    store = await create_store(db, org_id=org.id)

    response = await client.post(
        f"/api/stores/{store.id}/layouts",
        json={"rows": 5, "cols": 5},
        headers=_org_headers(org.id),
    )

    assert response.status_code == 403


# ── POST /api/stores/{store_id}/layouts/{id}/activate ─────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_activate_sets_version_active_and_deactivates_others(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Activating one version deactivates all others for the same store."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)
    store = await create_store(db, org_id=org.id)
    v1 = await create_layout_version(db, store_id=store.id, version_number=1, is_active=True)
    v2 = await create_layout_version(db, store_id=store.id, version_number=2, is_active=False)

    response = await client.post(
        f"/api/stores/{store.id}/layouts/{v2.id}/activate",
        headers=_org_headers(org.id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(v2.id)
    assert body["is_active"] is True

    # Confirm v1 is now inactive via the list endpoint
    list_response = await client.get(
        f"/api/stores/{store.id}/layouts",
        headers=_org_headers(org.id),
    )
    versions = {v["id"]: v for v in list_response.json()}
    assert versions[str(v1.id)]["is_active"] is False
    assert versions[str(v2.id)]["is_active"] is True


@pytest.mark.usefixtures("bypass_auth")
async def test_activate_unknown_layout_returns_404(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Activating a non-existent layout version returns 404."""
    import uuid

    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)
    store = await create_store(db, org_id=org.id)

    response = await client.post(
        f"/api/stores/{store.id}/layouts/{uuid.uuid4()}/activate",
        headers=_org_headers(org.id),
    )

    assert response.status_code == 404


# ── GET /api/stores/{store_id}/layouts/active ─────────────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_get_active_layout_returns_active_version(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Returns the active layout version with an empty zones list."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.EMPLOYEE)
    store = await create_store(db, org_id=org.id)
    active = await create_layout_version(
        db, store_id=store.id, version_number=1, rows=4, cols=6, is_active=True
    )

    response = await client.get(
        f"/api/stores/{store.id}/layouts/active",
        headers=_org_headers(org.id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(active.id)
    assert body["is_active"] is True
    assert body["rows"] == 4
    assert body["cols"] == 6
    assert body["zones"] == []


@pytest.mark.usefixtures("bypass_auth")
async def test_get_active_layout_returns_404_when_none_active(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Returns 404 when no layout version is active for the store."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.EMPLOYEE)
    store = await create_store(db, org_id=org.id)
    # Create an inactive version only
    await create_layout_version(db, store_id=store.id, version_number=1, is_active=False)

    response = await client.get(
        f"/api/stores/{store.id}/layouts/active",
        headers=_org_headers(org.id),
    )

    assert response.status_code == 404


# ── GET /api/stores/{store_id}/layouts ────────────────────────────────────────


@pytest.mark.usefixtures("bypass_auth")
async def test_list_layout_versions_ordered_by_version_number(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Returns all versions ordered ascending by version_number."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.EMPLOYEE)
    store = await create_store(db, org_id=org.id)
    # Insert out of order to verify sorting
    await create_layout_version(db, store_id=store.id, version_number=3)
    await create_layout_version(db, store_id=store.id, version_number=1)
    await create_layout_version(db, store_id=store.id, version_number=2)

    response = await client.get(
        f"/api/stores/{store.id}/layouts",
        headers=_org_headers(org.id),
    )

    assert response.status_code == 200
    numbers = [v["version_number"] for v in response.json()]
    assert numbers == [1, 2, 3]


@pytest.mark.usefixtures("bypass_auth")
async def test_list_layout_versions_empty(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Returns an empty list when the store has no layout versions."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.EMPLOYEE)
    store = await create_store(db, org_id=org.id)

    response = await client.get(
        f"/api/stores/{store.id}/layouts",
        headers=_org_headers(org.id),
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.usefixtures("bypass_auth")
async def test_list_layout_versions_scoped_to_store(
    client: AsyncClient,
    db: AsyncSession,
    test_user: User,
) -> None:
    """Versions from other stores are not included."""
    org = await create_org(db)
    await create_membership(db, org_id=org.id, user_id=test_user.id, org_role=OrgRole.OWNER)
    store_a = await create_store(db, org_id=org.id, name="Store A")
    store_b = await create_store(db, org_id=org.id, name="Store B")
    target = await create_layout_version(db, store_id=store_a.id, version_number=1)
    await create_layout_version(db, store_id=store_b.id, version_number=1)

    response = await client.get(
        f"/api/stores/{store_a.id}/layouts",
        headers=_org_headers(org.id),
    )

    assert response.status_code == 200
    ids = [v["id"] for v in response.json()]
    assert ids == [str(target.id)]
