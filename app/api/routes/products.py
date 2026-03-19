from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.orgs.deps import get_current_org_membership, require_org_role
from app.core.database import get_db
from app.models.org_membership import OrgMembership
from app.models.product import Product
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductListResponse,
    ProductSupplierAdd,
    ProductSupplierUpdate,
    ProductSupplierResponse,
)
from app.services import product_service

router = APIRouter(prefix="/api/products", tags=["products"])


# ── Helpers ──


async def _get_product_or_404(
    db: AsyncSession,
    product_id: uuid.UUID,
    org_id: uuid.UUID,
) -> Product:
    product = await product_service.get_product(db, product_id, org_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return product


# ── Product CRUD ──


@router.get("", response_model=list[ProductListResponse])
async def list_products(
    membership: OrgMembership = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db),
) -> list[Product]:
    """List all products for the current org."""
    return await product_service.list_products(db, membership.org_id)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: uuid.UUID,
    membership: OrgMembership = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db),
) -> ProductResponse:
    """Get a single product with its suppliers."""
    product = await _get_product_or_404(db, product_id, membership.org_id)
    return ProductResponse.model_validate(product)


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    body: ProductCreate,
    membership: OrgMembership = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db),
) -> ProductResponse:
    """Create a new product."""

    product = await product_service.create_product(
        db=db,
        org_id=membership.org_id,
        name=body.name,
        description=body.description,
        sku=body.sku,
        category=body.category,
    )
    return ProductResponse.model_validate(product)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: uuid.UUID,
    body: ProductUpdate,
    membership: OrgMembership = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db),
) -> ProductResponse:
    """Update a product's details."""
    product = await _get_product_or_404(db, product_id, membership.org_id)
    product = await product_service.update_product(
        db,
        product,
        name=body.name,
        description=body.description,
        sku=body.sku,
        category=body.category,
    )
    return ProductResponse.model_validate(product)


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: uuid.UUID,
    membership: OrgMembership = Depends(require_org_role("ORG_OWNER", "ORG_ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a product. Owner/Admin only."""
    product = await _get_product_or_404(db, product_id, membership.org_id)
    await product_service.delete_product(db, product)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Product-Supplier link management ──


@router.get(
    "/{product_id}/suppliers",
    response_model=list[ProductSupplierResponse],
)
async def list_product_suppliers(
    product_id: uuid.UUID,
    membership: OrgMembership = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db),
) -> list[ProductSupplierResponse]:
    """List all suppliers linked to a product."""
    # Ensure the product belongs to the org
    await _get_product_or_404(db, product_id, membership.org_id)
    links = await product_service.list_product_suppliers(db, product_id)
    return [ProductSupplierResponse.model_validate(link) for link in links]


@router.post(
    "/{product_id}/suppliers",
    response_model=ProductSupplierResponse,
    status_code=201,
)
async def add_supplier_to_product(
    product_id: uuid.UUID,
    body: ProductSupplierAdd,
    membership: OrgMembership = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db),
) -> ProductSupplierResponse:
    """Link a supplier to a product."""
    # Verify product belongs to org
    await _get_product_or_404(db, product_id, membership.org_id)

    # Verify supplier belongs to same org
    supplier = await product_service.get_supplier_in_org(
        db, body.supplier_id, membership.org_id
    )
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found in this organization",
        )

    # Check for existing link
    existing = await product_service.get_product_supplier_link(
        db, product_id, body.supplier_id
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Supplier is already linked to this product",
        )

    link = await product_service.add_supplier_to_product(
        db, product_id, body.supplier_id
    )
    return ProductSupplierResponse.model_validate(link)


@router.patch(
    "/{product_id}/suppliers/{supplier_id}",
    response_model=ProductSupplierResponse,
)
async def update_product_supplier(
    product_id: uuid.UUID,
    supplier_id: uuid.UUID,
    body: ProductSupplierUpdate,
    membership: OrgMembership = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db),
) -> ProductSupplierResponse:
    """Update the is_active flag on a product-supplier link."""
    await _get_product_or_404(db, product_id, membership.org_id)

    link = await product_service.get_product_supplier_link(db, product_id, supplier_id)
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier is not linked to this product",
        )

    link = await product_service.update_product_supplier_link(db, link, body.is_active)
    return ProductSupplierResponse.model_validate(link)


@router.delete(
    "/{product_id}/suppliers/{supplier_id}",
    status_code=204,
)
async def remove_supplier_from_product(
    product_id: uuid.UUID,
    supplier_id: uuid.UUID,
    membership: OrgMembership = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Remove a supplier link from a product entirely."""
    await _get_product_or_404(db, product_id, membership.org_id)

    link = await product_service.get_product_supplier_link(db, product_id, supplier_id)
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier is not linked to this product",
        )

    await product_service.remove_supplier_from_product(db, link)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
