# Developer Guide

Everything you need to contribute to the EasyInventory API: coding standards, testing, how to add a new feature end-to-end, and the Makefile command reference.

---

## Table of Contents

- [Development Workflow](#development-workflow)
- [Code Formatting & Linting](#code-formatting--linting)
- [Type Checking (mypy)](#type-checking-mypy)
- [Testing](#testing)
  - [Test Suite 1: Mocked Database (tests/)](#test-suite-1-mocked-database-tests)
  - [Test Suite 2: Real Database (testsv2/)](#test-suite-2-real-database-testsv2)
  - [Writing New Tests](#writing-new-tests)
- [Adding a New Feature (End-to-End Walkthrough)](#adding-a-new-feature-end-to-end-walkthrough)
- [Key Patterns & Conventions](#key-patterns--conventions)
- [Git Workflow](#git-workflow)
- [Makefile Reference](#makefile-reference)

---

## Development Workflow

1. **Pull the latest `development`** — `git pull origin development`
2. **Create a feature branch** — `git checkout -b feature/my-feature`
3. **Make your changes** — follow the patterns below
4. **Run formatting** — `make format`
5. **Run type checking** — `make typecheck`
6. **Run tests** — `make test` (mocked) and/or `make test-v2` (real DB)
7. **Commit** — use conventional commit messages
8. **Push and create a PR** into `development`

> **Branch strategy:** Feature branches are merged into `development`. When a release is ready, `development` is merged into `main`.

---

## Code Formatting & Linting

The project uses [Black](https://github.com/psf/black) for code formatting.

**Configuration** (in `pyproject.toml`):

```toml
[tool.black]
line-length = 88
target-version = ["py311"]
```

### Commands

```bash
# Check formatting (does not modify files)
make format-check

# Auto-fix formatting
make format

# These are equivalent
make format-fix
```

```powershell
# Windows (PowerShell)
python -m black --check app/ tests/ testsv2/    # check
python -m black app/ tests/ testsv2/            # fix
```

### Rules

- **Line length:** 88 characters max.
- **All Python files** in `app/`, `tests/`, and `testsv2/` are formatted.
- **Run `make format` before committing.** CI will reject unformatted code.

---

## Type Checking (mypy)

The project uses [mypy](https://mypy-lang.org/) for static type checking.

**Configuration** (in `mypy.ini`):

```ini
[mypy]
python_version = 3.11
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True        # All functions MUST have type annotations
ignore_missing_imports = True

[mypy-tests.*]
disallow_untyped_defs = False       # Tests are exempt from type annotations
```

### Commands

```bash
make typecheck

# Or directly
python -m mypy app/
```

```powershell
# Windows
python -m mypy app/
```

### Rules

- **All functions in `app/` must have type annotations** — both parameters and return types.
- **Tests are exempt** — the `[mypy-tests.*]` section relaxes the requirement.
- **Third-party imports are ignored** — `ignore_missing_imports = True` prevents errors from untyped packages.

---

## Testing

The project has **two independent test suites** with different trade-offs:

| Suite | Location | Database | Speed | Fidelity |
|---|---|---|---|---|
| **Suite 1** | `tests/` | Mocked (no Postgres needed) | Fast | Tests logic in isolation |
| **Suite 2** | `testsv2/` | Real Postgres (transaction rollback) | Slower | Tests real SQL behavior |

Both suites use `pytest` with `asyncio_mode = "auto"` (async tests run without extra decorators).

---

### Test Suite 1: Mocked Database (`tests/`)

Uses `httpx.AsyncClient` with `ASGITransport` to call the app directly — no network, no database. All dependencies (database sessions, auth) are mocked or patched.

**Run all Suite 1 tests:**

```bash
make test
```

**Run only unit tests:**

```bash
make test-unit
```

**Run only functional tests:**

```bash
make test-functional
```

```powershell
# Windows
python -m pytest tests/ -v
python -m pytest tests/unit/ -v
python -m pytest tests/functional/ -v
```

**How it works:**

```python
# tests/conftest.py
@pytest.fixture
def app():
    return create_app()

@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

**When to use:** For fast feedback during development, logic that doesn't depend on real SQL queries, testing route authorization, testing error handling.

---

### Test Suite 2: Real Database (`testsv2/`)

Runs against a **real PostgreSQL instance** with transaction-per-test rollback for isolation. Each test gets a real database session wrapped in a transaction that is always rolled back — so every test starts with a clean database.

**Step 1:** Start the test database (separate from the dev database):

```bash
make test-db
```

This starts a Docker container named `easyinventory-test-db` on port **5433** (not 5432, so it doesn't conflict with dev).

**Step 2:** Run Suite 2 tests:

```bash
make test-v2
```

This automatically runs `alembic upgrade head` on the test database before running tests.

**Step 3:** Stop the test database when done:

```bash
make test-db-stop
```

```powershell
# Windows — manual equivalent of make test-db
docker run -d --name easyinventory-test-db `
  -e POSTGRES_USER=test `
  -e POSTGRES_PASSWORD=test `
  -e POSTGRES_DB=easyinventory_test `
  -p 5433:5432 `
  postgres:16-alpine

# Wait for Postgres to be ready, then:
$env:DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5433/easyinventory_test"
python -m alembic upgrade head
python -m pytest testsv2/ -v
```

**How it works:**

The `testsv2/conftest.py` creates a session fixture using the **nested transaction pattern**:

1. An **outer transaction** is opened on a raw connection.
2. A **session** is created, bound to that connection.
3. A **nested transaction** (SAVEPOINT) is started.
4. When application code calls `session.commit()`, it only releases the savepoint (not the outer transaction).
5. After the test, the outer transaction is **rolled back** — nothing is written to the database.

This gives each test a completely clean database without needing to truncate tables.

**When to use:** For testing real SQL queries, Alembic migrations, complex joins, race conditions, anything where mocking the database would hide bugs.

---

### Writing New Tests

#### Suite 1 test example (mocked)

```python
# tests/unit/test_my_feature.py
import pytest
from unittest.mock import AsyncMock, patch

from app.myfeature.service import get_thing


@pytest.mark.asyncio
async def test_get_thing_not_found():
    db = AsyncMock()
    db.execute.return_value.scalar_one_or_none.return_value = None

    with pytest.raises(NotFound, match="Thing not found"):
        await get_thing(db, thing_id=uuid4(), org_id=uuid4())
```

#### Suite 2 test example (real database)

```python
# testsv2/integration/test_my_feature.py
import pytest
from testsv2.factories import create_org_with_owner, create_supplier


@pytest.mark.asyncio
async def test_create_supplier(db):
    org, owner, _ = await create_org_with_owner(db)

    supplier = await create_supplier(
        db,
        org_id=org.id,
        name="Test Supplier",
    )

    assert supplier.id is not None
    assert supplier.name == "Test Supplier"
    assert supplier.org_id == org.id
```

#### Using factories (`testsv2/`)

The `testsv2/factories.py` module provides helper functions that INSERT real rows:

| Factory | What It Creates |
|---|---|
| `create_user(db, ...)` | A `User` row with defaults |
| `create_org(db, ...)` | An `Organization` row |
| `create_membership(db, ...)` | An `OrgMembership` row |
| `create_org_with_owner(db, ...)` | An org + user + OWNER membership (returns tuple) |
| `create_supplier(db, ...)` | A `Supplier` row |
| `create_product(db, ...)` | A `Product` row |
| `create_product_supplier(db, ...)` | A `ProductSupplier` link |

All factories accept keyword arguments to override defaults.

---

## Adding a New Feature (End-to-End Walkthrough)

Let's walk through adding a **Categories** feature — a new domain that manages product categories within an organization.

### Step 1: Create the model

```python
# app/models/category.py
from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class Category(BaseModel):
    __tablename__ = "categories"

    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
```

### Step 2: Register the model

```python
# app/models/__init__.py — add the import
from app.models.category import Category  # noqa: F401
```

### Step 3: Generate a migration

```bash
make migrate-generate msg="add categories table"
```

Review the generated file in `alembic/versions/`, then apply:

```bash
make migrate
# or: docker compose exec api alembic upgrade head
```

### Step 4: Create schemas

```python
# app/categories/schemas.py
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class CategoryResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    description: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
```

### Step 5: Create the service

```python
# app/categories/service.py
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models.category import Category


async def list_categories(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> list[Category]:
    result = await db.execute(
        select(Category).where(Category.org_id == org_id)
    )
    return list(result.scalars().all())


async def get_category(
    db: AsyncSession,
    category_id: uuid.UUID,
    org_id: uuid.UUID,
) -> Category | None:
    result = await db.execute(
        select(Category).where(
            Category.id == category_id,
            Category.org_id == org_id,
        )
    )
    return result.scalar_one_or_none()


async def create_category(
    db: AsyncSession,
    org_id: uuid.UUID,
    name: str,
    description: str | None = None,
) -> Category:
    category = Category(org_id=org_id, name=name, description=description)
    db.add(category)
    await db.flush()
    await db.refresh(category)
    return category
```

### Step 6: Create the routes

```python
# app/categories/routes.py
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.orgs.deps import get_current_org_membership
from app.core.database import get_db
from app.models.org_membership import OrgMembership
from app.categories.schemas import CategoryCreate, CategoryResponse
from app.categories import service as category_service

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[CategoryResponse])
async def list_categories(
    membership: OrgMembership = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db),
) -> list:
    return await category_service.list_categories(db, membership.org_id)


@router.post("", response_model=CategoryResponse, status_code=201)
async def create_category(
    body: CategoryCreate,
    membership: OrgMembership = Depends(get_current_org_membership),
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    category = await category_service.create_category(
        db=db,
        org_id=membership.org_id,
        name=body.name,
        description=body.description,
    )
    return CategoryResponse.model_validate(category)
```

### Step 7: Register the routes

```python
# app/main.py — in create_app(), add:
from app.categories.routes import router as categories_router
app.include_router(categories_router)
```

### Step 8: Don't forget

- [ ] Create `app/categories/__init__.py` (empty file)
- [ ] Add tests (both suites)
- [ ] Add a factory to `testsv2/factories.py`
- [ ] Run `make format && make typecheck && make test`

---

## Key Patterns & Conventions

### 1. Domain module structure

Every domain follows the same 3-file pattern. See [Architecture: Domain Module Pattern](architecture.md#domain-module-pattern).

### 2. Service functions are pure database operations

Services accept `db: AsyncSession` and other arguments. They return ORM model instances or domain-specific dataclasses (e.g. when the result involves aggregates that don't map 1:1 to a model). They **never** raise `HTTPException` — they raise domain exceptions from `app/core/exceptions.py`.

### 3. Org-scoping

Every business query **must** filter by `org_id`. Never return data across organizations. The `org_id` comes from the authenticated membership, **never** from the request body.

### 4. UUID primary keys

All models use UUIDs. Use `uuid.uuid4()` for test data. Never use sequential integers.

### 5. Pydantic v2 conventions

```python
class MyResponse(BaseModel):
    id: uuid.UUID
    name: str
    model_config = {"from_attributes": True}  # Required for ORM → schema conversion
```

### 6. Async everywhere

All database operations are async. Use `await` for every SQLAlchemy call:

```python
result = await db.execute(select(Model).where(...))
items = list(result.scalars().all())
```

### 7. Import style

```python
# Absolute imports only
from app.core.database import get_db       # ✓
from ..core.database import get_db         # ✗ Never use relative imports
```

### 8. Dependencies via injection

Auth, org membership, and database sessions are injected via FastAPI `Depends()`. Never create sessions manually in routes.

---

## Git Workflow

### Branching model

```
main           ← production releases only
└── development  ← integration branch (merge feature branches here)
    ├── feature/add-categories
    ├── fix/supplier-delete-cascade
    └── refactor/auth-middleware
```

All feature branches are created from and merged back into `development`. When a release is ready, `development` is merged into `main`.

### Commit messages

Use conventional commit format:

```
feat: add categories CRUD endpoints
fix: prevent duplicate product-supplier links
test: add integration tests for supplier service
refactor: extract invite logic into service module
chore: update dev-requirements.txt
docs: add deployment guide
```

### PR checklist

Before creating a pull request into `development`:

- [ ] `make format` — code is formatted
- [ ] `make typecheck` — no type errors
- [ ] `make test` — all Suite 1 tests pass
- [ ] `make test-v2` — all Suite 2 tests pass (if you changed DB logic)
- [ ] New migrations reviewed (if any)
- [ ] New endpoints documented

---

## Makefile Reference

All commands assume you have a virtualenv activated (or are using Docker).

| Command | Description |
|---|---|
| `make run` | Start dev server via Docker Compose (`docker compose up`) |
| `make build` | Start dev server with image rebuild (`docker compose up --build`) |
| `make test` | Run Suite 1 tests (mocked DB) |
| `make test-unit` | Run Suite 1 unit tests only |
| `make test-functional` | Run Suite 1 functional tests only |
| `make test-db` | Start a dedicated test Postgres container (port 5433) |
| `make test-db-stop` | Stop and remove the test Postgres container |
| `make test-v2` | Run Suite 2 tests (requires `make test-db` first) |
| `make lint` | Run formatting check + type checking |
| `make format` | Auto-format all Python files with Black |
| `make format-check` | Check formatting without modifying files |
| `make format-fix` | Same as `make format` |
| `make typecheck` | Run mypy type checking on `app/` |
| `make migrate` | Apply all pending Alembic migrations |
| `make migrate-generate msg="..."` | Auto-generate a new migration |
| `make migrate-down` | Rollback the last migration |
| `make db-shell` | Open a psql shell to the dev database |
| `make clean` | Remove `__pycache__`, `.pytest_cache`, `.mypy_cache` |

---

## Related Guides

- [Architecture](architecture.md) — System design, RBAC, exception system
- [API Reference](api-reference.md) — All endpoints
- [Getting Started](getting-started.md) — Setup and installation
- [Deployment Guide](deployment-guide.md) — Production deployment
- [Troubleshooting](troubleshooting.md) — Common issues and fixes
