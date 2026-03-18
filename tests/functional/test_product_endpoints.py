import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock

from app.api.deps import get_current_org_membership
from app.core.database import get_db
from app.models.org_membership import OrgMembership
from app.models.product import Product
from app.models.product_supplier import ProductSupplier
from app.models.supplier import Supplier

_NOW = datetime(2026, 3, 17, tzinfo=timezone.utc)


def _mock_membership(role="ORG_EMPLOYEE", org_id=None):
    mock = MagicMock(spec=OrgMembership)
    mock.id = uuid.uuid4()
    mock.org_id = org_id or uuid.uuid4()
    mock.org_role = role
    mock.is_active = True
    mock.user_id = uuid.uuid4()
    return mock


def _mock_product(org_id=None, product_id=None, suppliers=None):
    mock = MagicMock(spec=Product)
    mock.id = product_id or uuid.uuid4()
    mock.org_id = org_id or uuid.uuid4()
    mock.name = "Test Product"
    mock.description = "A test product"
    mock.sku = "TST-001"
    mock.category = "Produce"
    mock.created_at = _NOW
    mock.updated_at = _NOW
    mock.product_suppliers = suppliers or []
    return mock


def _mock_supplier(org_id=None, supplier_id=None):
    mock = MagicMock(spec=Supplier)
    mock.id = supplier_id or uuid.uuid4()
    mock.org_id = org_id or uuid.uuid4()
    mock.name = "Test Supplier"
    return mock


def _mock_product_supplier(product_id=None, supplier_id=None, is_active=True):
    mock = MagicMock(spec=ProductSupplier)
    mock.id = uuid.uuid4()
    mock.product_id = product_id or uuid.uuid4()
    mock.supplier_id = supplier_id or uuid.uuid4()
    mock.is_active = is_active
    mock.created_at = _NOW
    mock.updated_at = _NOW

    supplier_mock = MagicMock(spec=Supplier)
    supplier_mock.name = "Test Supplier"
    mock.supplier = supplier_mock
    return mock


@contextmanager
def _product_dependency_overrides(app, membership):
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_org_membership] = lambda: membership
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_org_membership, None)


# ── Product CRUD endpoints ──


async def test_list_products_returns_200(app, client):
    membership = _mock_membership()

    with _product_dependency_overrides(app, membership):
        with patch("app.services.product_service.list_products", return_value=[]):
            response = await client.get(
                "/api/products",
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 200
    assert response.json() == []


async def test_get_product_returns_200(app, client):
    membership = _mock_membership()
    product = _mock_product(org_id=membership.org_id)

    with _product_dependency_overrides(app, membership):
        with patch("app.services.product_service.get_product", return_value=product):
            response = await client.get(
                f"/api/products/{product.id}",
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Product"
    assert data["suppliers"] == []


async def test_get_nonexistent_product_returns_404(app, client):
    membership = _mock_membership()

    with _product_dependency_overrides(app, membership):
        with patch("app.services.product_service.get_product", return_value=None):
            response = await client.get(
                f"/api/products/{uuid.uuid4()}",
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 404


async def test_create_product_returns_201(app, client):
    membership = _mock_membership()
    new_product = _mock_product(org_id=membership.org_id)

    with _product_dependency_overrides(app, membership):
        with patch(
            "app.services.product_service.create_product", return_value=new_product
        ):
            response = await client.post(
                "/api/products",
                json={"name": "Test Product", "sku": "TST-001"},
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 201
    assert response.json()["name"] == "Test Product"


async def test_update_product_returns_200(app, client):
    membership = _mock_membership()
    product = _mock_product(org_id=membership.org_id)
    updated = _mock_product(org_id=membership.org_id, product_id=product.id)
    updated.name = "Updated Product"

    with _product_dependency_overrides(app, membership):
        with patch("app.services.product_service.get_product", return_value=product):
            with patch(
                "app.services.product_service.update_product", return_value=updated
            ):
                response = await client.put(
                    f"/api/products/{product.id}",
                    json={"name": "Updated Product"},
                    headers={"Authorization": "Bearer fake"},
                )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Product"


async def test_delete_product_requires_admin(app, client):
    """ORG_EMPLOYEE cannot delete products."""
    membership = _mock_membership(role="ORG_EMPLOYEE")

    with _product_dependency_overrides(app, membership):
        response = await client.delete(
            f"/api/products/{uuid.uuid4()}",
            headers={"Authorization": "Bearer fake"},
        )
    assert response.status_code == 403


async def test_delete_product_works_for_owner(app, client):
    membership = _mock_membership(role="ORG_OWNER")
    product = _mock_product(org_id=membership.org_id)

    with _product_dependency_overrides(app, membership):
        with patch("app.services.product_service.get_product", return_value=product):
            with patch("app.services.product_service.delete_product"):
                response = await client.delete(
                    f"/api/products/{product.id}",
                    headers={"Authorization": "Bearer fake"},
                )
    assert response.status_code == 204


async def test_products_returns_401_without_token(client):
    response = await client.get("/api/products")
    assert response.status_code == 401


# ── Product-Supplier link endpoints ──


async def test_list_product_suppliers_returns_200(app, client):
    membership = _mock_membership()
    product = _mock_product(org_id=membership.org_id)
    ps_link = _mock_product_supplier(product_id=product.id, supplier_id=uuid.uuid4())

    with _product_dependency_overrides(app, membership):
        with patch("app.services.product_service.get_product", return_value=product):
            with patch(
                "app.services.product_service.list_product_suppliers",
                return_value=[ps_link],
            ):
                response = await client.get(
                    f"/api/products/{product.id}/suppliers",
                    headers={"Authorization": "Bearer fake"},
                )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["is_active"] is True


async def test_add_supplier_to_product_returns_201(app, client):
    membership = _mock_membership()
    product = _mock_product(org_id=membership.org_id)
    supplier = _mock_supplier(org_id=membership.org_id)
    ps_link = _mock_product_supplier(product_id=product.id, supplier_id=supplier.id)

    with _product_dependency_overrides(app, membership):
        with patch("app.services.product_service.get_product", return_value=product):
            with patch(
                "app.services.product_service.get_supplier_in_org",
                return_value=supplier,
            ):
                with patch(
                    "app.services.product_service.get_product_supplier_link",
                    return_value=None,
                ):
                    with patch(
                        "app.services.product_service.add_supplier_to_product",
                        return_value=ps_link,
                    ):
                        response = await client.post(
                            f"/api/products/{product.id}/suppliers",
                            json={"supplier_id": str(supplier.id)},
                            headers={"Authorization": "Bearer fake"},
                        )
    assert response.status_code == 201
    assert response.json()["is_active"] is True


async def test_add_supplier_to_product_409_duplicate(app, client):
    membership = _mock_membership()
    product = _mock_product(org_id=membership.org_id)
    supplier = _mock_supplier(org_id=membership.org_id)
    existing_link = _mock_product_supplier(
        product_id=product.id, supplier_id=supplier.id
    )

    with _product_dependency_overrides(app, membership):
        with patch("app.services.product_service.get_product", return_value=product):
            with patch(
                "app.services.product_service.get_supplier_in_org",
                return_value=supplier,
            ):
                with patch(
                    "app.services.product_service.get_product_supplier_link",
                    return_value=existing_link,
                ):
                    response = await client.post(
                        f"/api/products/{product.id}/suppliers",
                        json={"supplier_id": str(supplier.id)},
                        headers={"Authorization": "Bearer fake"},
                    )
    assert response.status_code == 409


async def test_add_supplier_404_wrong_org(app, client):
    membership = _mock_membership()
    product = _mock_product(org_id=membership.org_id)

    with _product_dependency_overrides(app, membership):
        with patch("app.services.product_service.get_product", return_value=product):
            with patch(
                "app.services.product_service.get_supplier_in_org",
                return_value=None,
            ):
                response = await client.post(
                    f"/api/products/{product.id}/suppliers",
                    json={"supplier_id": str(uuid.uuid4())},
                    headers={"Authorization": "Bearer fake"},
                )
    assert response.status_code == 404


async def test_update_product_supplier_is_active(app, client):
    membership = _mock_membership()
    product = _mock_product(org_id=membership.org_id)
    supplier_id = uuid.uuid4()
    ps_link = _mock_product_supplier(
        product_id=product.id, supplier_id=supplier_id, is_active=True
    )
    updated_link = _mock_product_supplier(
        product_id=product.id, supplier_id=supplier_id, is_active=False
    )

    with _product_dependency_overrides(app, membership):
        with patch("app.services.product_service.get_product", return_value=product):
            with patch(
                "app.services.product_service.get_product_supplier_link",
                return_value=ps_link,
            ):
                with patch(
                    "app.services.product_service.update_product_supplier_link",
                    return_value=updated_link,
                ):
                    response = await client.patch(
                        f"/api/products/{product.id}/suppliers/{supplier_id}",
                        json={"is_active": False},
                        headers={"Authorization": "Bearer fake"},
                    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False


async def test_remove_supplier_from_product_returns_204(app, client):
    membership = _mock_membership()
    product = _mock_product(org_id=membership.org_id)
    supplier_id = uuid.uuid4()
    ps_link = _mock_product_supplier(product_id=product.id, supplier_id=supplier_id)

    with _product_dependency_overrides(app, membership):
        with patch("app.services.product_service.get_product", return_value=product):
            with patch(
                "app.services.product_service.get_product_supplier_link",
                return_value=ps_link,
            ):
                with patch("app.services.product_service.remove_supplier_from_product"):
                    response = await client.delete(
                        f"/api/products/{product.id}/suppliers/{supplier_id}",
                        headers={"Authorization": "Bearer fake"},
                    )
    assert response.status_code == 204


async def test_remove_nonexistent_supplier_link_returns_404(app, client):
    membership = _mock_membership()
    product = _mock_product(org_id=membership.org_id)

    with _product_dependency_overrides(app, membership):
        with patch("app.services.product_service.get_product", return_value=product):
            with patch(
                "app.services.product_service.get_product_supplier_link",
                return_value=None,
            ):
                response = await client.delete(
                    f"/api/products/{product.id}/suppliers/{uuid.uuid4()}",
                    headers={"Authorization": "Bearer fake"},
                )
    assert response.status_code == 404
