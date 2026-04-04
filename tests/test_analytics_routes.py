"""Route-level tests for analytics endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.deps import get_current_user
from app.core.database import get_db
from app.main import create_app
from app.orgs.deps import get_current_org_membership
from app.stores.deps import get_store_from_path
from app.analytics.schemas import (
    UnzonedSummary,
    ZoneInventorySummaryResponse,
)

STORE_ID = str(uuid.uuid4())
MOCK_RESPONSE = ZoneInventorySummaryResponse(
    layout_id=uuid.uuid4(),
    layout_version=1,
    rows=10,
    cols=8,
    zones=[],
    fixtures=[],
    unzoned_summary=UnzonedSummary(
        total_items=0,
        total_quantity=0,
        low_stock_count=0,
        out_of_stock_count=0,
    ),
)


@pytest.fixture
def app():
    application = create_app()

    mock_store = MagicMock()
    mock_store.id = uuid.UUID(STORE_ID)

    application.dependency_overrides[get_current_user] = lambda: MagicMock()
    application.dependency_overrides[get_current_org_membership] = lambda: MagicMock()
    application.dependency_overrides[get_store_from_path] = lambda: mock_store
    application.dependency_overrides[get_db] = lambda: AsyncMock()

    yield application

    application.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestZoneInventorySummaryRoute:
    @pytest.mark.asyncio
    async def test_returns_200_with_valid_data(self, client):
        """Endpoint returns 200 when service succeeds."""
        with patch(
            "app.analytics.routes.service.get_zone_inventory_summary"
        ) as mock_svc:
            mock_svc.return_value = MOCK_RESPONSE

            response = await client.get(
                f"/api/stores/{STORE_ID}/analytics/zone-inventory-summary"
            )

            assert response.status_code == 200
            assert response.json() == {
                "layout_id": str(MOCK_RESPONSE.layout_id),
                "layout_version": MOCK_RESPONSE.layout_version,
                "rows": MOCK_RESPONSE.rows,
                "cols": MOCK_RESPONSE.cols,
                "zones": [],
                "fixtures": [],
                "unzoned_summary": {
                    "total_items": MOCK_RESPONSE.unzoned_summary.total_items,
                    "total_quantity": MOCK_RESPONSE.unzoned_summary.total_quantity,
                    "low_stock_count": MOCK_RESPONSE.unzoned_summary.low_stock_count,
                    "out_of_stock_count": MOCK_RESPONSE.unzoned_summary.out_of_stock_count,
                },
            }
