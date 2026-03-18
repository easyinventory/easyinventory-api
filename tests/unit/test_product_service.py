import uuid
from unittest.mock import AsyncMock, MagicMock

from app.services.product_service import (
    create_product,
    update_product,
    delete_product,
    get_product,
    add_supplier_to_product,
    get_product_supplier_link,
    update_product_supplier_link,
    remove_supplier_from_product,
    get_supplier_in_org,
)
from app.models.product import Product
from app.models.product_supplier import ProductSupplier
from app.models.supplier import Supplier

# ── Product CRUD ──


async def test_create_product():
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    result = await create_product(
        db=mock_db,
        org_id=uuid.uuid4(),
        name="Apples",
        description="Fresh red apples",
        sku="APL-001",
        category="Produce",
    )

    mock_db.add.assert_called_once()
    added = mock_db.add.call_args[0][0]
    assert isinstance(added, Product)
    assert added.name == "Apples"
    assert added.description == "Fresh red apples"
    assert added.sku == "APL-001"
    assert added.category == "Produce"


async def test_create_product_minimal():
    """Only name is required."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    await create_product(
        db=mock_db,
        org_id=uuid.uuid4(),
        name="Oranges",
    )

    added = mock_db.add.call_args[0][0]
    assert added.name == "Oranges"
    assert added.description is None
    assert added.sku is None
    assert added.category is None


async def test_update_product_changes_fields():
    product = MagicMock(spec=Product)
    product.name = "Old Name"
    product.description = "Old desc"

    mock_db = AsyncMock()

    await update_product(
        mock_db,
        product,
        name="New Name",
        description="New desc",
    )

    assert product.name == "New Name"
    assert product.description == "New desc"


async def test_update_product_skips_none():
    """None values should not overwrite existing data."""
    product = MagicMock(spec=Product)
    product.name = "Keep This"

    mock_db = AsyncMock()

    await update_product(
        mock_db,
        product,
        name=None,
        description="New Description",
    )

    mock_db.flush.assert_called_once()


async def test_delete_product():
    product = MagicMock(spec=Product)
    mock_db = AsyncMock()

    await delete_product(mock_db, product)
    mock_db.delete.assert_called_once_with(product)


async def test_get_product_returns_none():
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    result = await get_product(mock_db, uuid.uuid4(), uuid.uuid4())
    assert result is None


# ── Product-Supplier link management ──


async def test_add_supplier_to_product():
    link_id = uuid.uuid4()
    product_id = uuid.uuid4()
    supplier_id = uuid.uuid4()

    mock_link = MagicMock(spec=ProductSupplier)
    mock_link.id = link_id
    mock_link.product_id = product_id
    mock_link.supplier_id = supplier_id
    mock_link.is_active = True

    mock_result = MagicMock()
    mock_result.scalar_one.return_value = mock_link

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute.return_value = mock_result

    result = await add_supplier_to_product(mock_db, product_id, supplier_id)

    mock_db.add.assert_called_once()
    added = mock_db.add.call_args[0][0]
    assert isinstance(added, ProductSupplier)
    assert added.product_id == product_id
    assert added.supplier_id == supplier_id
    assert added.is_active is True
    assert result == mock_link


async def test_get_product_supplier_link_returns_none():
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    result = await get_product_supplier_link(mock_db, uuid.uuid4(), uuid.uuid4())
    assert result is None


async def test_update_product_supplier_link_sets_inactive():
    link = MagicMock(spec=ProductSupplier)
    link.is_active = True
    mock_db = AsyncMock()

    result = await update_product_supplier_link(mock_db, link, False)

    assert link.is_active is False
    mock_db.flush.assert_called_once()


async def test_remove_supplier_from_product():
    link = MagicMock(spec=ProductSupplier)
    mock_db = AsyncMock()

    await remove_supplier_from_product(mock_db, link)
    mock_db.delete.assert_called_once_with(link)


async def test_get_supplier_in_org_returns_none():
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    result = await get_supplier_in_org(mock_db, uuid.uuid4(), uuid.uuid4())
    assert result is None


async def test_get_supplier_in_org_returns_supplier():
    mock_supplier = MagicMock(spec=Supplier)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_supplier
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    result = await get_supplier_in_org(mock_db, uuid.uuid4(), uuid.uuid4())
    assert result == mock_supplier
