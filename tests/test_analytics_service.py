"""Unit tests for analytics service — zone inventory summary."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.analytics.schemas import StockStatus
from app.analytics.service import _classify_stock, get_zone_inventory_summary

# ── _classify_stock tests ─────────────────────────────────────────────────────


class TestClassifyStock:
    def test_out_of_stock_zero(self):
        assert _classify_stock(0, 10) == StockStatus.OUT

    def test_out_of_stock_negative(self):
        assert _classify_stock(-1, 10) == StockStatus.OUT

    def test_low_stock_at_threshold(self):
        assert _classify_stock(5, 5) == StockStatus.LOW

    def test_low_stock_below_threshold(self):
        assert _classify_stock(3, 5) == StockStatus.LOW

    def test_ok_above_threshold(self):
        assert _classify_stock(10, 5) == StockStatus.OK

    def test_ok_no_threshold(self):
        assert _classify_stock(10, None) == StockStatus.OK

    def test_zero_no_threshold(self):
        assert _classify_stock(0, None) == StockStatus.OUT


# ── get_zone_inventory_summary tests ──────────────────────────────────────────


class TestGetZoneInventorySummary:
    @pytest.mark.asyncio
    async def test_raises_not_found_when_no_active_layout(self):
        """Should raise NotFound when the store has no active layout."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        from app.core.exceptions import NotFound

        with pytest.raises(NotFound):
            await get_zone_inventory_summary(db, uuid.uuid4())
