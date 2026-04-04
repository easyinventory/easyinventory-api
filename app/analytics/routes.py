"""Routes for analytics endpoints."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/stores/{store_id}/analytics", tags=["analytics"])
