# EasyInventory API — Backend Refactoring Plan

## Moderate Restructure + Python Patterns Audit + Real-Database Testing

---

## 1. Problem Summary

### 1.1 Structural Issues

**`org_service.py` is a god module (~280 lines, 15+ functions).** It handles member CRUD, org CRUD, user lookups, system-admin queries (`list_all_orgs`, `list_all_users`), and ownership transfer. When Sprint 2 adds inventory management, this file will either grow further or developers will be unsure where new service logic should go.

**`core/cognito.py` mixes hot-path and cold-path concerns.** Token verification (`verify_token`, `get_signing_key`) runs on every authenticated request. Admin operations (`invite_cognito_user`, `delete_cognito_user`) run rarely. These have different failure modes, different test strategies, and different dependency profiles (JWKS cache vs. boto3 client). They shouldn't live in the same module.

**`core/` is a grab-bag.** It contains config, database, bootstrap seeding, Cognito integration, middleware, role constants, and domain exceptions — seven unrelated concerns. `bootstrap.py` alone is ~180 lines with seed data embedded directly in the module.

**`admin.py` routes file does too many things.** It handles org CRUD (create, list, rename, delete), ownership transfer, org member introspection, and user management (list, delete). These are at least three distinct admin sub-domains.

**`api/deps.py` bundles unrelated dependencies.** Auth dependencies (`get_current_user`, `require_role`) and org-membership dependencies (`get_current_org_membership`, `require_org_role`) serve different purposes but live in one file. As new dependency patterns emerge (e.g., `require_inventory_access`), this file will grow unwieldy.

**Schemas are organized by layer, not by domain.** `schemas/admin.py` contains both org schemas and user schemas. As features grow, you'll have `schemas/inventory.py` mixing stock-level schemas with adjustment schemas with alert schemas.

### 1.2 Python Patterns Audit

**What's already done well:**

- **Domain exceptions with centralized handler.** `core/exceptions.py` defines a clean hierarchy (`AppError` → `OwnerProtected`, `AdminHierarchyViolation`, etc.) and `main.py` translates them to HTTP responses via `@app.exception_handler(AppError)`. This keeps services free of HTTP concerns — they're testable outside FastAPI.
- **Dependency injection chain.** `get_current_user` → `require_role` / `require_org_role` is a textbook FastAPI pattern. The `require_role` factory returning a closure is clean and composable.
- **Service layer separation.** Routes handle HTTP concerns (status codes, request/response serialization), services handle business logic. This boundary is consistently maintained across all features.
- **`invite_service.py` as orchestration.** Extracting the invite flow (find user → Cognito → placeholder → membership) into a dedicated service eliminated duplication between `admin.py` and `orgs.py`. Good instinct.
- **Permission helpers in `api/permissions.py`.** Raising domain exceptions (not `HTTPException`) makes these reusable from background jobs or CLI commands. The naming convention (`assert_not_owner`, `assert_admin_hierarchy`) is clear and consistent.
- **Bootstrap seeder is idempotent.** `run_bootstrap` handles three scenarios (new user, existing user without membership, existing user with membership) and is safe to call on every startup. The seed data approach is practical for demos.
- **Async-first throughout.** Consistent use of `async/await`, `AsyncSession`, and `create_async_engine`. No accidental sync blocking.
- **Structured JSON logging.** `RequestLoggingMiddleware` with correlation IDs, sensitive field sanitization, and error body capture is production-grade.

**What needs improvement:**

- **`org_service.py` violates single responsibility.** It contains member management, org CRUD, user queries, admin-only aggregations, and ownership transfer. Functions like `get_user_by_id` and `find_user_by_email` are generic user operations, not org operations.
- **No `user_service` for user queries.** `get_user_by_id` lives in `org_service` despite having nothing to do with orgs. `user_service.py` exists but only has `get_or_create_user` and `delete_user_completely`.
- **Seed data embedded in `bootstrap.py`.** `SEED_SUPPLIERS` and `SEED_PRODUCTS` are hardcoded Python dicts in a module that also handles startup logic. This makes the seed data hard to modify, hard to test independently, and bloats a file that should be about bootstrapping.
- **Services return `list[dict]` instead of models.** `list_all_orgs`, `list_all_users`, and `list_org_members` manually construct dicts from query results. This bypasses Pydantic validation and makes the return types opaque. Services should return models or typed dataclasses; routes should handle serialization.
- **Admin routes file mixes three domains.** Org CRUD, user management, and org-member introspection are all in `admin.py`. When you add admin endpoints for inventory or analytics, this file will become unmanageable.
- **`cognito.py` is a monolith.** Token verification (hot path, cached, read-only) lives alongside user administration (cold path, network calls, write operations). A bug in invite logic shouldn't risk breaking token verification.
- **No type aliases for service return types.** Functions return `Optional[User]`, `Optional[OrgMembership]`, `list[dict]` — the `list[dict]` cases especially lose all type safety.

### 1.3 Testing Issues

**Every test mocks the database.** All 90+ tests use `MagicMock`/`AsyncMock` for the database session. This means:
- Tests verify that code calls `db.execute()` with *something*, not that the query actually works.
- Schema changes (column renames, new constraints) don't break any tests until they hit production.
- Complex queries (the subquery joins in `list_all_orgs`, `list_all_users`) are completely untested against real SQL.
- The `side_effect` chains in test fixtures are brittle — they break if the service adds one more query.

**Functional tests mock the entire dependency chain.** Tests like `test_admin_can_create_org_with_new_email` have 7 levels of nested `with patch(...)` context managers. This is testing the mocking setup more than the actual code.

**No test database infrastructure.** The CI workflow spins up a Postgres container but only for the test job's environment — there are no fixtures that actually connect to it.

**No factory functions for test data.** Each test file has its own `_mock_user()`, `_mock_membership()`, `_mock_supplier()` helpers that create `MagicMock` objects. These don't exercise model constructors, don't validate constraints, and drift out of sync with the real models.

---

## 2. Target Architecture

Keep models, database, and core infrastructure centralized. Split services, routes, and schemas by domain. Add a real-database test layer.

```
app/
├── main.py                      # App factory, CORS, lifespan
├── core/                        # Shared infrastructure (centralized)
│   ├── config.py                # Pydantic Settings
│   ├── database.py              # Engine, session, Base, get_db
│   ├── exceptions.py            # Domain exception hierarchy
│   ├── roles.py                 # SystemRole, OrgRole constants
│   └── middleware.py            # Request logging, correlation IDs
│
├── auth/                        # Authentication (was split across core/ and api/)
│   ├── cognito_token.py         # JWKS fetch, verify_token, get_signing_key (HOT PATH)
│   ├── cognito_admin.py         # invite_cognito_user, delete_cognito_user (COLD PATH)
│   ├── deps.py                  # get_current_user, require_role (auth-only deps)
│   └── routes.py                # GET /api/me
│
├── models/                      # All SQLAlchemy models (centralized)
│   ├── __init__.py              # Re-exports all models for Alembic
│   ├── base.py                  # BaseModel (UUID pk + created_at)
│   ├── user.py
│   ├── organization.py
│   ├── org_membership.py
│   ├── supplier.py
│   ├── product.py
│   └── product_supplier.py
│
├── orgs/                        # Org membership + settings domain
│   ├── deps.py                  # get_current_org_membership, require_org_role
│   ├── permissions.py           # assert_not_owner, assert_admin_hierarchy, etc.
│   ├── routes.py                # /api/orgs/* endpoints
│   ├── schemas.py               # OrgMembershipResponse, InviteMemberRequest, etc.
│   └── service.py               # Member CRUD: list, invite, update_role, deactivate, etc.
│
├── admin/                       # System admin domain
│   ├── routes_orgs.py           # /api/admin/orgs/* (org CRUD, transfer, member list)
│   ├── routes_users.py          # /api/admin/users/* (list, delete)
│   ├── schemas.py               # OrgListItem, CreateOrgRequest, UserListItem
│   └── service.py               # list_all_orgs, list_all_users, rename_org, delete_org, transfer
│
├── suppliers/                   # Supplier domain
│   ├── routes.py
│   ├── schemas.py
│   └── service.py
│
├── products/                    # Product domain
│   ├── routes.py
│   ├── schemas.py
│   └── service.py
│
├── users/                       # User domain (shared user operations)
│   └── service.py               # get_or_create_user, get_user_by_id, find_by_email, delete
│
├── invites/                     # Invite orchestration (cross-cutting)
│   └── service.py               # invite_user_to_org (uses users/, orgs/, auth/)
│
├── bootstrap/                   # Startup seeding (extracted from core/)
│   ├── seeder.py                # run_bootstrap logic
│   └── seed_data.py             # SEED_SUPPLIERS, SEED_PRODUCTS (data only)
│
├── health/                      # Health check
│   └── routes.py
│
tests/
├── conftest.py                  # Shared fixtures: real DB session, test client, factories
├── factories.py                 # Factory functions: create_user, create_org, create_membership, etc.
├── unit/                        # Pure logic tests (no DB, no HTTP) — permissions, roles, config
├── integration/                 # Real DB tests — service layer against Postgres (NEW)
└── functional/                  # HTTP endpoint tests — full request/response cycle (NEW: real DB)
```

---

## 3. Key Design Decisions

### 3.1 Models stay centralized

SQLAlchemy models have cross-domain `relationship()` declarations (`OrgMembership.user`, `Product.product_suppliers`, `ProductSupplier.supplier`). Moving models into feature folders would create circular imports and fight against Alembic's single metadata registry. The `models/` directory stays flat and centralized.

### 3.2 Services split by domain, not by layer

Instead of one `services/` directory with `org_service.py`, `product_service.py`, etc., each domain folder contains its own `service.py`. This means a developer working on products only needs to look at `products/routes.py`, `products/schemas.py`, and `products/service.py` — three files in one directory.

**Import convention:**

```python
# Inside products/routes.py
from app.products.service import list_products, create_product

# Cross-domain import (products needs to verify supplier exists)
from app.users.service import get_user_by_id
```

### 3.3 `org_service.py` is broken into three pieces

| Current function | New home | Reason |
|---|---|---|
| `list_org_members`, `get_membership_by_id`, `find_existing_membership`, `create_membership`, `update_role`, `set_active_status`, `delete_membership` | `orgs/service.py` | Core org-membership operations |
| `list_all_orgs`, `get_org_by_id`, `rename_org`, `delete_org`, `transfer_ownership`, `list_all_users` | `admin/service.py` | System-admin operations |
| `get_user_by_id`, `find_user_by_email`, `create_placeholder_user` | `users/service.py` | Generic user operations |

### 3.4 Cognito is split by access pattern

| Current function | New home | Reason |
|---|---|---|
| `get_jwks`, `get_signing_key`, `verify_token`, `get_email_from_access_token` | `auth/cognito_token.py` | Hot path — runs on every request, cached, read-only |
| `invite_cognito_user`, `delete_cognito_user`, `_get_cognito_client` | `auth/cognito_admin.py` | Cold path — runs rarely, makes network calls, writes |

### 3.5 Admin routes split by sub-domain

| Current file | New home |
|---|---|
| `POST/GET/PATCH/DELETE /api/admin/orgs/*`, `POST transfer-ownership`, `GET members` | `admin/routes_orgs.py` |
| `GET /api/admin/users`, `DELETE /api/admin/users/{id}` | `admin/routes_users.py` |
| `GET /api/admin/status` | `admin/routes_orgs.py` (or remove — it's a test endpoint) |

### 3.6 Bootstrap is extracted from core/

`bootstrap.py` moves to `bootstrap/seeder.py` and its embedded seed data moves to `bootstrap/seed_data.py`. This makes it easy to modify seed data without touching bootstrap logic, and keeps `core/` focused on infrastructure.

### 3.7 Auth dependencies separate from org dependencies

| Current location | New home |
|---|---|
| `get_current_user`, `require_role`, `bearer_scheme` | `auth/deps.py` |
| `get_current_org_membership`, `require_org_role` | `orgs/deps.py` |

---

## 4. Testing Overhaul: Real-Database Tests

This is the most impactful change in the entire refactoring. Moving from mocked database tests to real Postgres tests will catch SQL bugs, constraint violations, and query regressions that your current suite can't detect.

### 4.1 Architecture

```
tests/
├── conftest.py            # DB engine, session fixtures, app with real DB
├── factories.py           # Helper functions that INSERT real rows
├── unit/                  # Pure logic: permissions, roles, config, cognito token
├── integration/           # Service functions against real Postgres
│   ├── conftest.py        # Integration-specific fixtures if needed
│   ├── test_user_service.py
│   ├── test_org_service.py
│   ├── test_admin_service.py
│   ├── test_invite_service.py
│   ├── test_product_service.py
│   └── test_supplier_service.py
└── functional/            # HTTP endpoints against real Postgres
    ├── conftest.py        # Auth bypass fixtures
    ├── test_health.py
    ├── test_auth.py
    ├── test_orgs.py
    ├── test_products.py
    ├── test_suppliers.py
    └── test_admin.py
```

### 4.2 Database fixtures (`tests/conftest.py`)

```python
import asyncio
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import create_app

# ── Test database engine ──
# Uses the DATABASE_URL from .env / CI environment.
# In CI, this points to the postgres service container.
# Locally, point it to a test database:
#   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/easyinventory_test

test_engine = create_async_engine(settings.DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop():
    """Use a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    """Create all tables once at the start of the test session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a transactional database session for each test.

    Each test runs inside a transaction that is ROLLED BACK after
    the test completes — so tests never leave data behind and
    cannot interfere with each other.
    """
    async with test_engine.connect() as conn:
        transaction = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)

        try:
            yield session
        finally:
            await transaction.rollback()
            await session.close()


@pytest.fixture
def app(db: AsyncSession):
    """Create an app instance that uses the test DB session."""
    application = create_app()

    async def _override_get_db():
        yield db

    application.dependency_overrides[get_db] = _override_get_db
    return application


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client wired to the test app with real DB."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

**Key design: transaction-per-test rollback.** Each test gets a real database session wrapped in a transaction. After the test finishes (pass or fail), the transaction is rolled back. This means every test starts with a clean database, tests can run in any order, and there's zero cleanup logic needed. This is the standard pattern used by SQLAlchemy's own test suite and recommended by the FastAPI documentation.

### 4.3 Factory functions (`tests/factories.py`)

Replace all `_mock_user()`, `_mock_membership()` helpers with functions that create real database rows:

```python
"""
Test data factories — create real DB rows with sensible defaults.

Every factory INSERTs a real row and returns the model instance.
Override any field by passing keyword arguments.

Usage:
    user = await create_user(db, email="admin@test.com")
    org = await create_org(db, name="Acme Corp")
    membership = await create_membership(
        db, org_id=org.id, user_id=user.id, role="ORG_OWNER"
    )
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import OrgRole, SystemRole
from app.models.organization import Organization
from app.models.org_membership import OrgMembership
from app.models.product import Product
from app.models.product_supplier import ProductSupplier
from app.models.supplier import Supplier
from app.models.user import User


async def create_user(
    db: AsyncSession,
    *,
    email: str = "test@example.com",
    cognito_sub: str | None = None,
    system_role: str = SystemRole.USER,
    is_active: bool = True,
) -> User:
    """Create a real User row in the test database."""
    user = User(
        cognito_sub=cognito_sub or f"sub-{uuid.uuid4().hex[:12]}",
        email=email,
        system_role=system_role,
        is_active=is_active,
    )
    db.add(user)
    await db.flush()
    return user


async def create_org(
    db: AsyncSession,
    *,
    name: str = "Test Organization",
) -> Organization:
    """Create a real Organization row."""
    org = Organization(name=name)
    db.add(org)
    await db.flush()
    return org


async def create_membership(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    org_role: str = OrgRole.EMPLOYEE,
    is_active: bool = True,
) -> OrgMembership:
    """Create a real OrgMembership row."""
    membership = OrgMembership(
        org_id=org_id,
        user_id=user_id,
        org_role=org_role,
        is_active=is_active,
    )
    db.add(membership)
    await db.flush()
    return membership


async def create_supplier(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    name: str = "Test Supplier",
    contact_email: str | None = "supplier@test.com",
) -> Supplier:
    """Create a real Supplier row."""
    supplier = Supplier(
        org_id=org_id,
        name=name,
        contact_email=contact_email,
    )
    db.add(supplier)
    await db.flush()
    return supplier


async def create_product(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    name: str = "Test Product",
    sku: str | None = "TST-001",
    category: str | None = "General",
) -> Product:
    """Create a real Product row."""
    product = Product(
        org_id=org_id,
        name=name,
        sku=sku,
        category=category,
    )
    db.add(product)
    await db.flush()
    return product


async def create_product_supplier(
    db: AsyncSession,
    *,
    product_id: uuid.UUID,
    supplier_id: uuid.UUID,
    is_active: bool = True,
) -> ProductSupplier:
    """Create a real ProductSupplier link row."""
    link = ProductSupplier(
        product_id=product_id,
        supplier_id=supplier_id,
        is_active=is_active,
    )
    db.add(link)
    await db.flush()
    return link


async def create_org_with_owner(
    db: AsyncSession,
    *,
    org_name: str = "Test Org",
    owner_email: str = "owner@test.com",
) -> tuple[Organization, User, OrgMembership]:
    """Convenience: create an org + owner user + owner membership in one call."""
    owner = await create_user(db, email=owner_email)
    org = await create_org(db, name=org_name)
    membership = await create_membership(
        db, org_id=org.id, user_id=owner.id, org_role=OrgRole.OWNER
    )
    return org, owner, membership
```

### 4.4 Example: integration test (service layer + real DB)

```python
# tests/integration/test_org_service.py

from app.orgs.service import (
    list_org_members,
    create_membership,
    update_role,
    set_active_status,
    delete_membership,
)
from app.core.roles import OrgRole
from tests.factories import create_org_with_owner, create_user, create_membership


async def test_list_org_members_returns_all_members(db):
    """Real query against Postgres — verifies JOIN + ORDER BY."""
    org, owner, _ = await create_org_with_owner(db)

    employee = await create_user(db, email="employee@test.com")
    await create_membership(
        db, org_id=org.id, user_id=employee.id, org_role=OrgRole.EMPLOYEE
    )

    members = await list_org_members(db, org.id)

    assert len(members) == 2
    emails = {m["email"] for m in members}
    assert "owner@test.com" in emails
    assert "employee@test.com" in emails


async def test_update_role_persists_change(db):
    """Verify role change is actually written to the database."""
    org, _, _ = await create_org_with_owner(db)
    user = await create_user(db, email="promote@test.com")
    membership = await create_membership(
        db, org_id=org.id, user_id=user.id, org_role=OrgRole.EMPLOYEE
    )

    await update_role(db, membership, OrgRole.ADMIN)

    # Re-fetch from DB to verify persistence
    refreshed = await db.get(type(membership), membership.id)
    assert refreshed.org_role == OrgRole.ADMIN


async def test_delete_membership_removes_from_db(db):
    """Verify deletion is real, not just an in-memory change."""
    org, _, _ = await create_org_with_owner(db)
    user = await create_user(db, email="remove@test.com")
    membership = await create_membership(
        db, org_id=org.id, user_id=user.id, org_role=OrgRole.VIEWER
    )

    await delete_membership(db, membership)

    result = await db.get(type(membership), membership.id)
    assert result is None
```

### 4.5 Example: functional test (HTTP endpoint + real DB)

```python
# tests/functional/conftest.py

import pytest
from unittest.mock import patch

from app.auth.deps import get_current_user
from app.models.user import User
from tests.factories import create_user, create_org_with_owner


@pytest.fixture
def bypass_auth(app, db):
    """
    Fixture that bypasses Cognito token verification and injects
    a real test user. Returns a helper to set the authenticated user.

    Usage:
        async def test_something(client, bypass_auth, db):
            user = await create_user(db, email="me@test.com")
            bypass_auth(user)
            response = await client.get("/api/me", headers=AUTH_HEADER)
    """
    _user = None

    async def _override():
        return _user

    def _set_user(user: User):
        nonlocal _user
        _user = user
        app.dependency_overrides[get_current_user] = _override

    yield _set_user

    app.dependency_overrides.pop(get_current_user, None)


# Convenience header — the actual token doesn't matter since auth is bypassed
AUTH_HEADER = {"Authorization": "Bearer test-token"}
```

```python
# tests/functional/test_products.py

from tests.factories import (
    create_org_with_owner,
    create_membership,
    create_product,
    create_supplier,
    create_user,
)
from tests.functional.conftest import AUTH_HEADER
from app.core.roles import OrgRole


async def test_list_products_returns_only_own_org(client, bypass_auth, db):
    """Products from other orgs should never leak through."""
    # Setup: two orgs, each with a product
    org1, owner1, _ = await create_org_with_owner(db, owner_email="a@test.com")
    org2, owner2, _ = await create_org_with_owner(
        db, org_name="Other Org", owner_email="b@test.com"
    )

    await create_product(db, org_id=org1.id, name="My Product")
    await create_product(db, org_id=org2.id, name="Their Product")

    bypass_auth(owner1)
    response = await client.get("/api/products", headers=AUTH_HEADER)

    assert response.status_code == 200
    products = response.json()
    assert len(products) == 1
    assert products[0]["name"] == "My Product"


async def test_create_product_persists_to_db(client, bypass_auth, db):
    """POST /api/products should create a real row in the database."""
    org, owner, _ = await create_org_with_owner(db)
    bypass_auth(owner)

    response = await client.post(
        "/api/products",
        json={"name": "New Product", "sku": "NEW-001", "category": "Produce"},
        headers=AUTH_HEADER,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New Product"
    assert data["sku"] == "NEW-001"

    # Verify it's actually in the database
    from app.models.product import Product
    product = await db.get(Product, data["id"])
    assert product is not None
    assert product.name == "New Product"


async def test_delete_product_requires_admin_role(client, bypass_auth, db):
    """ORG_EMPLOYEE should get 403 when trying to delete."""
    org, owner, _ = await create_org_with_owner(db)
    employee = await create_user(db, email="employee@test.com")
    await create_membership(
        db, org_id=org.id, user_id=employee.id, org_role=OrgRole.EMPLOYEE
    )
    product = await create_product(db, org_id=org.id)

    bypass_auth(employee)
    response = await client.delete(
        f"/api/products/{product.id}", headers=AUTH_HEADER
    )

    assert response.status_code == 403
```

### 4.6 What stays mocked vs. what becomes real

| Layer | Before | After |
|-------|--------|-------|
| Database session | `AsyncMock()` everywhere | Real Postgres via transaction rollback |
| SQLAlchemy queries | Never actually executed | Executed against real tables |
| Cognito token verification | `patch("verify_token")` | Still mocked — no real Cognito in tests |
| Cognito admin (invite/delete) | `patch("invite_cognito_user")` | Still mocked — no real Cognito in tests |
| HTTP request/response | Real via `httpx.AsyncClient` | Same — no change |
| Model construction | `MagicMock(spec=User)` | `User(...)` via factory functions |
| Service layer logic | Mocked DB, real Python logic | Real DB, real Python logic |
| Permission helpers | Already tested without mocks | No change |

**Rule of thumb:** Mock external services (Cognito, email, S3). Never mock your own database.

### 4.7 CI configuration update

Your CI already starts a Postgres container. The only change needed is to ensure `DATABASE_URL` in the test step points to it, and to add a migration step:

```yaml
# In .github/workflows/ci.yml, under the test job steps:
- name: Run migrations
  env:
    DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/test
  run: alembic upgrade head

- name: Test
  env:
    DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/test
    COGNITO_REGION: us-east-2
    COGNITO_USER_POOL_ID: test
    COGNITO_APP_CLIENT_ID: test
    BOOTSTRAP_ADMIN_EMAIL: ""
  run: pytest
```

### 4.8 Local test database setup

Add to the README and `Makefile`:

```makefile
# Makefile addition
test-db:
	docker run -d --name easyinventory-test-db \
	  -e POSTGRES_USER=test \
	  -e POSTGRES_PASSWORD=test \
	  -e POSTGRES_DB=easyinventory_test \
	  -p 5433:5432 \
	  postgres:16-alpine

test:
	DATABASE_URL=postgresql+asyncpg://test:test@localhost:5433/easyinventory_test \
	  alembic upgrade head && \
	DATABASE_URL=postgresql+asyncpg://test:test@localhost:5433/easyinventory_test \
	  python -m pytest tests/ -v
```

### 4.9 Migration strategy for existing tests

Don't rewrite all tests at once. The approach:

1. Set up the new `conftest.py` with real DB fixtures.
2. Write new integration tests for the most critical services (`org_service`, `product_service`).
3. Write new functional tests for one feature end-to-end (products is a good candidate).
4. Gradually replace mock-heavy functional tests as you touch each feature in Sprint 2.
5. Keep the existing unit tests for pure logic (permissions, roles, config, cognito token) — these don't need a database and are fine with mocks.

---

## 5. Migration Steps

### Step 1: Create the directory skeleton

```bash
mkdir -p app/{auth,orgs,admin,suppliers,products,users,invites,bootstrap,health}
mkdir -p tests/{integration,functional}
```

**Commit:** `refactor: create domain-based directory skeleton`

### Step 2: Split `core/cognito.py` into auth module

| From | To |
|------|-----|
| `core/cognito.py` → `get_jwks`, `get_signing_key`, `verify_token`, `get_email_from_access_token` | `auth/cognito_token.py` |
| `core/cognito.py` → `invite_cognito_user`, `delete_cognito_user`, `_get_cognito_client` | `auth/cognito_admin.py` |
| `api/deps.py` → `get_current_user`, `require_role`, `bearer_scheme` | `auth/deps.py` |
| `api/routes/auth.py` | `auth/routes.py` |

Delete `core/cognito.py` and `api/routes/auth.py` after migration.

Update all imports across the codebase.

**Commit:** `refactor: extract auth module from core/cognito and api/deps`

### Step 3: Split `api/deps.py` org dependencies into `orgs/`

| From | To |
|------|-----|
| `api/deps.py` → `get_current_org_membership`, `require_org_role` | `orgs/deps.py` |
| `api/permissions.py` | `orgs/permissions.py` |
| `api/routes/orgs.py` | `orgs/routes.py` |
| `schemas/org.py` | `orgs/schemas.py` |

**Commit:** `refactor: migrate org dependencies, routes, schemas to orgs/`

### Step 4: Break up `org_service.py`

| From (`services/org_service.py`) | To |
|------|-----|
| `list_org_members`, `get_membership_by_id`, `find_existing_membership`, `create_membership`, `update_role`, `set_active_status`, `delete_membership` | `orgs/service.py` |
| `list_all_orgs`, `get_org_by_id`, `rename_org`, `delete_org`, `transfer_ownership`, `list_all_users` | `admin/service.py` |
| `get_user_by_id`, `find_user_by_email`, `create_placeholder_user` | `users/service.py` |

Merge existing `services/user_service.py` content into `users/service.py`.

**Commit:** `refactor: split org_service into orgs/, admin/, users/ services`

### Step 5: Migrate admin routes and schemas

| From | To |
|------|-----|
| `api/routes/admin.py` (org CRUD + transfer + member introspection) | `admin/routes_orgs.py` |
| `api/routes/admin.py` (user list + delete) | `admin/routes_users.py` |
| `schemas/admin.py` | `admin/schemas.py` |

**Commit:** `refactor: split admin routes by sub-domain`

### Step 6: Migrate products and suppliers

| From | To |
|------|-----|
| `api/routes/products.py` | `products/routes.py` |
| `schemas/product.py` | `products/schemas.py` |
| `services/product_service.py` | `products/service.py` |
| `api/routes/suppliers.py` | `suppliers/routes.py` |
| `schemas/supplier.py` | `suppliers/schemas.py` |
| `services/supplier_service.py` | `suppliers/service.py` |

**Commit:** `refactor: migrate products and suppliers to domain folders`

### Step 7: Extract bootstrap and invites

| From | To |
|------|-----|
| `core/bootstrap.py` (logic) | `bootstrap/seeder.py` |
| `core/bootstrap.py` (seed data) | `bootstrap/seed_data.py` |
| `services/invite_service.py` | `invites/service.py` |
| `api/routes/health.py` | `health/routes.py` |

**Commit:** `refactor: extract bootstrap seeder and invite service`

### Step 8: Update `main.py` router registration

```python
# app/main.py — updated imports
from app.health.routes import router as health_router
from app.auth.routes import router as auth_router
from app.orgs.routes import router as orgs_router
from app.admin.routes_orgs import router as admin_orgs_router
from app.admin.routes_users import router as admin_users_router
from app.suppliers.routes import router as suppliers_router
from app.products.routes import router as products_router

# ... in create_app():
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(orgs_router)
app.include_router(admin_orgs_router)
app.include_router(admin_users_router)
app.include_router(suppliers_router)
app.include_router(products_router)
```

**Commit:** `refactor: update main.py router registration for new structure`

### Step 9: Clean up empty directories

Delete:
- `app/api/` (all routes moved to domain folders)
- `app/schemas/` (all schemas moved to domain folders)
- `app/services/` (all services moved to domain folders)

Keep:
- `app/core/` (config, database, exceptions, roles, middleware)
- `app/models/` (all models stay centralized)

**Commit:** `refactor: remove empty legacy directories`

### Step 10: Set up real-database test infrastructure

Create:
- `tests/conftest.py` — real DB fixtures (Section 4.2)
- `tests/factories.py` — factory functions (Section 4.3)
- `tests/functional/conftest.py` — auth bypass fixture (Section 4.5)

Update `Makefile` with `test-db` target. Update CI to run migrations before tests.

**Do not delete existing tests yet.** The new infrastructure runs alongside the old tests.

**Commit:** `add: real-database test infrastructure with transaction rollback`

### Step 11: Write integration tests for critical services

Write real-DB integration tests for:
- `orgs/service.py` — member CRUD, the JOIN query in `list_org_members`
- `admin/service.py` — the complex subquery JOINs in `list_all_orgs` and `list_all_users`
- `products/service.py` — product-supplier link management, cascading deletes
- `users/service.py` — placeholder claiming flow (`get_or_create_user`)

These tests will catch query bugs that mock-based tests structurally cannot.

**Commit:** `test: add integration tests for service layer against real Postgres`

### Step 12: Write functional tests for one feature end-to-end

Rewrite `test_product_endpoints.py` using real DB + auth bypass (Section 4.5). This serves as the template for migrating other functional test files.

**Commit:** `test: rewrite product endpoint tests with real database`

### Step 13: Update README and Makefile

Update project structure in README. Add test database setup instructions. Document the testing philosophy (mock external services, never mock your own database).

**Commit:** `docs: update README with new project structure and testing guide`

---

## 6. Import Update Cheat Sheet

| Old import | New import |
|---|---|
| `from app.core.cognito import verify_token` | `from app.auth.cognito_token import verify_token` |
| `from app.core.cognito import invite_cognito_user` | `from app.auth.cognito_admin import invite_cognito_user` |
| `from app.core.cognito import delete_cognito_user` | `from app.auth.cognito_admin import delete_cognito_user` |
| `from app.api.deps import get_current_user` | `from app.auth.deps import get_current_user` |
| `from app.api.deps import require_role` | `from app.auth.deps import require_role` |
| `from app.api.deps import get_current_org_membership` | `from app.orgs.deps import get_current_org_membership` |
| `from app.api.deps import require_org_role` | `from app.orgs.deps import require_org_role` |
| `from app.api.permissions import ...` | `from app.orgs.permissions import ...` |
| `from app.services.org_service import ...` | `from app.orgs.service import ...` (member ops) |
| `from app.services.org_service import list_all_orgs` | `from app.admin.service import list_all_orgs` |
| `from app.services.org_service import get_user_by_id` | `from app.users.service import get_user_by_id` |
| `from app.services.org_service import find_user_by_email` | `from app.users.service import find_user_by_email` |
| `from app.services.org_service import create_placeholder_user` | `from app.users.service import create_placeholder_user` |
| `from app.services.product_service import ...` | `from app.products.service import ...` |
| `from app.services.supplier_service import ...` | `from app.suppliers.service import ...` |
| `from app.services.invite_service import ...` | `from app.invites.service import ...` |
| `from app.services.user_service import ...` | `from app.users.service import ...` |
| `from app.schemas.org import ...` | `from app.orgs.schemas import ...` |
| `from app.schemas.admin import ...` | `from app.admin.schemas import ...` |
| `from app.schemas.product import ...` | `from app.products.schemas import ...` |
| `from app.schemas.supplier import ...` | `from app.suppliers.schemas import ...` |
| `from app.schemas.user import ...` | `from app.auth.schemas import ...` (or `app.users.schemas`) |
| `from app.core.bootstrap import run_bootstrap` | `from app.bootstrap.seeder import run_bootstrap` |

---

## 7. Dependency Rules

1. **Domain modules can import from `core/` and `models/` freely.** These are shared infrastructure.
2. **Domain modules can import from other domain modules' `service.py`.** For example, `invites/service.py` imports from `users/service.py` and `orgs/service.py`. This is expected for orchestration services.
3. **Domain modules should NOT import from other domains' `routes.py` or `deps.py`.** If two route files need the same dependency, extract it to a shared location.
4. **`core/` never imports from domain modules.** It's the foundation layer.
5. **`models/` never imports from domain modules.** Models are the data layer — they define structure, not behavior.
6. **Test factories import from `models/` directly.** They need to construct real model instances.

---

## 8. Adding a New Feature (Post-Migration Checklist)

When Sprint 2 adds inventory management:

1. Create `app/inventory/` with `routes.py`, `schemas.py`, `service.py`
2. Create `app/models/inventory.py` (stock levels, adjustments, etc.) — centralized with all other models
3. Add `from app.models.inventory import *` to `models/__init__.py` for Alembic
4. Generate migration: `make migrate-generate msg="add inventory tables"`
5. Register the router in `main.py`: `app.include_router(inventory_router)`
6. Write factories in `tests/factories.py`: `create_stock_level()`, `create_adjustment()`
7. Write integration tests in `tests/integration/test_inventory_service.py`
8. Write functional tests in `tests/functional/test_inventory.py`
9. Done. No existing files modified except `main.py` (one line) and `models/__init__.py` (one line).

---

## 9. Files to Delete After Migration

| File/Directory | Reason |
|---|---|
| `app/api/deps.py` | Split into `auth/deps.py` and `orgs/deps.py` |
| `app/api/permissions.py` | Moved to `orgs/permissions.py` |
| `app/api/routes/auth.py` | Moved to `auth/routes.py` |
| `app/api/routes/admin.py` | Split into `admin/routes_orgs.py` and `admin/routes_users.py` |
| `app/api/routes/orgs.py` | Moved to `orgs/routes.py` |
| `app/api/routes/products.py` | Moved to `products/routes.py` |
| `app/api/routes/suppliers.py` | Moved to `suppliers/routes.py` |
| `app/api/routes/health.py` | Moved to `health/routes.py` |
| `app/schemas/` (entire directory) | Each schema file moved to its domain folder |
| `app/services/` (entire directory) | Each service file moved to its domain folder |
| `app/core/cognito.py` | Split into `auth/cognito_token.py` and `auth/cognito_admin.py` |
| `app/core/bootstrap.py` | Moved to `bootstrap/seeder.py` + `bootstrap/seed_data.py` |

---

## 10. Things NOT to Change

- **Alembic stays at the project root.** It works, it finds all models via `models/__init__.py`, and moving it adds zero value.
- **`core/database.py` stays.** The engine, session factory, and `Base` are genuinely shared infrastructure.
- **`core/middleware.py` stays.** Request logging is cross-cutting and doesn't belong to any domain.
- **`core/roles.py` stays.** Role constants are used across all domains.
- **`core/exceptions.py` stays.** The exception hierarchy and `@app.exception_handler` are shared infrastructure.
- **`docker-compose.yml`, `Dockerfile`, CI workflow.** No structural changes needed beyond the test migration step.

---

## 11. Estimated Effort

| Step | Time | Risk |
|------|------|------|
| Step 1: Directory skeleton | 10 min | Low |
| Step 2: Auth module extraction | 45 min | Medium — many import rewrites, Cognito tests need updates |
| Step 3: Org dependencies | 30 min | Low |
| Step 4: Break up org_service | 1 hour | Medium — largest file split, verify all callers |
| Step 5: Admin routes + schemas | 45 min | Medium — route registration changes |
| Step 6: Products + suppliers | 30 min | Low — straightforward move |
| Step 7: Bootstrap + invites | 20 min | Low |
| Step 8: Update main.py | 15 min | Low |
| Step 9: Cleanup | 10 min | Low |
| Step 10: Test infrastructure | 1–1.5 hours | Medium — DB fixture design, verify rollback works |
| Step 11: Integration tests | 2–3 hours | Low risk, high effort — writing new tests |
| Step 12: Functional test migration | 1–2 hours | Medium — rewriting one feature's tests |
| Step 13: Docs | 20 min | Low |
| **Total** | **~8–11 hours** | |

Recommend doing the structural migration (Steps 1–9) in one branch (`refactor/domain-based-structure`) and the testing overhaul (Steps 10–12) in a second branch (`refactor/real-db-tests`). Run `make lint` and `make test` after every step. The existing mock-based tests will continue passing throughout the structural migration since only import paths change — the function signatures and behavior are unchanged.
