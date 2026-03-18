from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

# ── Product schemas ──


class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    sku: Optional[str] = None
    category: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    sku: Optional[str] = None
    category: Optional[str] = None


class ProductSupplierInfo(BaseModel):
    """Nested supplier info returned inside a product response."""

    id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    description: Optional[str]
    sku: Optional[str]
    category: Optional[str]
    created_at: datetime
    updated_at: datetime
    suppliers: list[ProductSupplierInfo] = []

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    """Lightweight product response without nested suppliers."""

    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    description: Optional[str]
    sku: Optional[str]
    category: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Product-Supplier link schemas ──


class ProductSupplierAdd(BaseModel):
    supplier_id: uuid.UUID


class ProductSupplierUpdate(BaseModel):
    is_active: bool


class ProductSupplierResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
