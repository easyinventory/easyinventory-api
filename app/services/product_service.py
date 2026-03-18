from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.product import Product
from app.models.product_supplier import ProductSupplier
from app.models.supplier import Supplier

# ── Product CRUD ──


async def list_products(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> list[Product]:
    """List all products for an org, ordered by name."""
    stmt = select(Product).where(Product.org_id == org_id).order_by(Product.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_product(
    db: AsyncSession,
    product_id: uuid.UUID,
    org_id: uuid.UUID,
) -> Optional[Product]:
    """Get a single product (with its supplier links loaded)."""
    stmt = (
        select(Product)
        .where(Product.id == product_id, Product.org_id == org_id)
        .options(selectinload(Product.product_suppliers))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_product(
    db: AsyncSession,
    org_id: uuid.UUID,
    name: str,
    description: Optional[str] = None,
    sku: Optional[str] = None,
    category: Optional[str] = None,
) -> Product:
    """Create a new product."""
    product = Product(
        org_id=org_id,
        name=name,
        description=description,
        sku=sku,
        category=category,
    )
    db.add(product)
    await db.flush()
    await db.refresh(product, ["product_suppliers"])
    return product


async def update_product(
    db: AsyncSession,
    product: Product,
    **fields: object,
) -> Product:
    """Update a product's fields. Only non-None values are applied."""
    for key, value in fields.items():
        if value is not None:
            setattr(product, key, value)
    await db.flush()
    return product


async def delete_product(
    db: AsyncSession,
    product: Product,
) -> None:
    """Permanently delete a product (cascades to product_suppliers)."""
    await db.delete(product)
    await db.flush()


# ── Product-Supplier link management ──


async def list_product_suppliers(
    db: AsyncSession,
    product_id: uuid.UUID,
) -> list[ProductSupplier]:
    """List all supplier links for a product."""
    stmt = (
        select(ProductSupplier)
        .where(ProductSupplier.product_id == product_id)
        .options(selectinload(ProductSupplier.supplier))
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def add_supplier_to_product(
    db: AsyncSession,
    product_id: uuid.UUID,
    supplier_id: uuid.UUID,
) -> ProductSupplier:
    """Link a supplier to a product (active by default)."""
    link = ProductSupplier(
        product_id=product_id,
        supplier_id=supplier_id,
        is_active=True,
    )
    db.add(link)
    await db.flush()

    # Reload with supplier relationship populated
    stmt = (
        select(ProductSupplier)
        .where(ProductSupplier.id == link.id)
        .options(selectinload(ProductSupplier.supplier))
    )
    result = await db.execute(stmt)
    return result.scalar_one()


async def get_product_supplier_link(
    db: AsyncSession,
    product_id: uuid.UUID,
    supplier_id: uuid.UUID,
) -> Optional[ProductSupplier]:
    """Get a specific product-supplier link."""
    stmt = (
        select(ProductSupplier)
        .where(
            ProductSupplier.product_id == product_id,
            ProductSupplier.supplier_id == supplier_id,
        )
        .options(selectinload(ProductSupplier.supplier))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_product_supplier_link(
    db: AsyncSession,
    link: ProductSupplier,
    is_active: bool,
) -> ProductSupplier:
    """Update the is_active flag on a product-supplier link."""
    link.is_active = is_active
    await db.flush()
    return link


async def remove_supplier_from_product(
    db: AsyncSession,
    link: ProductSupplier,
) -> None:
    """Permanently remove a supplier link from a product."""
    await db.delete(link)
    await db.flush()


async def get_supplier_in_org(
    db: AsyncSession,
    supplier_id: uuid.UUID,
    org_id: uuid.UUID,
) -> Optional[Supplier]:
    """Verify a supplier belongs to the given org."""
    stmt = select(Supplier).where(
        Supplier.id == supplier_id,
        Supplier.org_id == org_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
