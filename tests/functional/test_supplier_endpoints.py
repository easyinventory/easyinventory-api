import uuid
from contextlib import contextmanager
from unittest.mock import patch, MagicMock, AsyncMock

from app.orgs.deps import get_current_org_membership
from app.core.database import get_db
from app.models.user import User
from app.models.org_membership import OrgMembership
from app.models.supplier import Supplier


def _mock_user(email="user@test.com"):
    mock = MagicMock(spec=User)
    mock.id = uuid.uuid4()
    mock.email = email
    mock.system_role = "SYSTEM_USER"
    mock.is_active = True
    return mock


def _mock_membership(role="ORG_EMPLOYEE", org_id=None):
    mock = MagicMock(spec=OrgMembership)
    mock.id = uuid.uuid4()
    mock.org_id = org_id or uuid.uuid4()
    mock.org_role = role
    mock.is_active = True
    mock.user_id = uuid.uuid4()
    return mock


def _mock_supplier(org_id=None, supplier_id=None):
    mock = MagicMock(spec=Supplier)
    mock.id = supplier_id or uuid.uuid4()
    mock.org_id = org_id or uuid.uuid4()
    mock.name = "Test Supplier"
    mock.contact_name = "Jane"
    mock.contact_email = "jane@supplier.com"
    mock.contact_phone = "555-1234"
    mock.notes = "Good supplier"
    mock.created_at = "2026-03-16T00:00:00+00:00"
    mock.updated_at = "2026-03-16T00:00:00+00:00"
    return mock


@contextmanager
def _supplier_dependency_overrides(app, membership):
    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_org_membership] = lambda: membership
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_org_membership, None)


async def test_list_suppliers_returns_200(app, client):
    membership = _mock_membership()

    with _supplier_dependency_overrides(app, membership):
        with patch("app.services.supplier_service.list_suppliers", return_value=[]):
            response = await client.get(
                "/api/suppliers",
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 200
    assert response.json() == []


async def test_create_supplier_returns_201(app, client):
    membership = _mock_membership()
    new_supplier = _mock_supplier(org_id=membership.org_id)

    with _supplier_dependency_overrides(app, membership):
        with patch(
            "app.services.supplier_service.create_supplier", return_value=new_supplier
        ):
            response = await client.post(
                "/api/suppliers",
                json={"name": "Test Supplier"},
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 201
    assert response.json()["name"] == "Test Supplier"


async def test_delete_requires_admin(app, client):
    """ORG_EMPLOYEE cannot delete suppliers."""
    membership = _mock_membership(role="ORG_EMPLOYEE")

    with _supplier_dependency_overrides(app, membership):
        response = await client.delete(
            f"/api/suppliers/{uuid.uuid4()}",
            headers={"Authorization": "Bearer fake"},
        )
    assert response.status_code == 403


async def test_delete_works_for_owner(app, client):
    membership = _mock_membership(role="ORG_OWNER")
    supplier = _mock_supplier(org_id=membership.org_id)

    with _supplier_dependency_overrides(app, membership):
        with patch("app.services.supplier_service.get_supplier", return_value=supplier):
            with patch("app.services.supplier_service.delete_supplier"):
                response = await client.delete(
                    f"/api/suppliers/{supplier.id}",
                    headers={"Authorization": "Bearer fake"},
                )
    assert response.status_code == 204


async def test_get_nonexistent_returns_404(app, client):
    membership = _mock_membership()

    with _supplier_dependency_overrides(app, membership):
        with patch("app.services.supplier_service.get_supplier", return_value=None):
            response = await client.get(
                f"/api/suppliers/{uuid.uuid4()}",
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 404


async def test_suppliers_returns_401_without_token(client):
    response = await client.get("/api/suppliers")
    assert response.status_code == 401
