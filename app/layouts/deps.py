from __future__ import annotations

import uuid

from fastapi import Depends, Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFound
from app.models.layout_version import LayoutVersion
from app.models.store import Store
from app.stores.deps import get_store_from_path


async def get_layout_from_path(
    layout_version_id: uuid.UUID = Path(..., description="Layout version ID"),
    store: Store = Depends(get_store_from_path),
    db: AsyncSession = Depends(get_db),
) -> LayoutVersion:
    """
    Extract ``layout_version_id`` from the path and validate it belongs to the store.

    Raises 404 if the layout version does not exist or belongs to a different store.
    """
    result = await db.execute(
        select(LayoutVersion).where(
            LayoutVersion.id == layout_version_id,
            LayoutVersion.store_id == store.id,
        )
    )
    layout = result.scalar_one_or_none()
    if layout is None:
        raise NotFound(
            f"Layout version {layout_version_id} not found for store {store.id}"
        )
    return layout
