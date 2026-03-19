from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.orgs.deps import (
    get_current_org_membership,
    require_org_role,
)
from app.core.database import get_db
from app.models.org_membership import OrgMembership
from app.models.supplier import Supplier
from app.schemas.supplier import (
    SupplierCreate,
    SupplierUpdate,
    SupplierResponse,
)
from app.services import supplier_service

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


async def _get_supplier_or_404(
    db: AsyncSession,
    supplier_id: uuid.UUID,
    org_id: uuid.UUID,
) -> Supplier:
    supplier = await supplier_service.get_supplier(db, supplier_id, org_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found",
        )
    return supplier


@router.get("", response_model=list[SupplierResponse])
async def list_suppliers(
    membership: OrgMembership = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db),
) -> list[Supplier]:
    """List all suppliers for the current org."""
    return await supplier_service.list_suppliers(db, membership.org_id)


@router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: uuid.UUID,
    membership: OrgMembership = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db),
) -> Supplier:
    """Get a single supplier by ID."""
    return await _get_supplier_or_404(db, supplier_id, membership.org_id)


@router.post("", response_model=SupplierResponse, status_code=201)
async def create_supplier(
    body: SupplierCreate,
    membership: OrgMembership = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db),
) -> Supplier:
    """Create a new supplier."""
    return await supplier_service.create_supplier(
        db=db,
        org_id=membership.org_id,
        name=body.name,
        contact_name=body.contact_name,
        contact_email=body.contact_email,
        contact_phone=body.contact_phone,
        notes=body.notes,
    )


@router.put("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: uuid.UUID,
    body: SupplierUpdate,
    membership: OrgMembership = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db),
) -> Supplier:
    """Update an existing supplier."""
    supplier = await _get_supplier_or_404(db, supplier_id, membership.org_id)

    return await supplier_service.update_supplier(
        db=db,
        supplier=supplier,
        name=body.name,
        contact_name=body.contact_name,
        contact_email=body.contact_email,
        contact_phone=body.contact_phone,
        notes=body.notes,
    )


@router.delete("/{supplier_id}", status_code=204)
async def delete_supplier(
    supplier_id: uuid.UUID,
    membership: OrgMembership = Depends(require_org_role("ORG_OWNER", "ORG_ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a supplier. Owner/Admin only."""
    supplier = await _get_supplier_or_404(db, supplier_id, membership.org_id)
    await supplier_service.delete_supplier(db, supplier)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
