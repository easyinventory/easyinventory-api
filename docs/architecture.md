# Architecture Guide

A deep dive into how the EasyInventory API is structured, how requests flow through the system, and how the major subsystems (authentication, authorization, database, exceptions) work together.

---

## Table of Contents

- [Project Structure](#project-structure)
- [Domain Module Pattern](#domain-module-pattern)
- [Architecture Overview](#architecture-overview)
- [Request Lifecycle](#request-lifecycle)
- [Multi-Tenancy](#multi-tenancy)
- [Authentication (AWS Cognito)](#authentication-aws-cognito)
- [Role-Based Access Control (RBAC)](#role-based-access-control-rbac)
- [Database & Models](#database--models)
- [Database Migrations (Alembic)](#database-migrations-alembic)
- [Domain Exception System](#domain-exception-system)
- [Bootstrap & Seed Data](#bootstrap--seed-data)

---

## Project Structure

```
easyinventory-api/
├── app/                         # All application source code
│   ├── main.py                  # App factory: creates FastAPI app, registers middleware,
│   │                            #   exception handlers, CORS, and all route modules
│   ├── __init__.py
│   │
│   ├── core/                    # Shared infrastructure (used by all domains)
│   │   ├── config.py            #   pydantic-settings: loads env vars into Settings class
│   │   ├── database.py          #   SQLAlchemy async engine, session factory, get_db dependency
│   │   ├── exceptions.py        #   Domain exception hierarchy (AppError and subclasses)
│   │   ├── middleware.py        #   Request logging, correlation IDs, JSON formatter
│   │   └── roles.py            #   SystemRole / OrgRole string constants
│   │
│   ├── auth/                    # Authentication domain (AWS Cognito)
│   │   ├── cognito_token.py     #   JWKS fetching, JWT verification (runs on every request)
│   │   ├── cognito_admin.py     #   Cognito admin ops: invite user, delete user (cold path)
│   │   ├── deps.py              #   FastAPI dependencies: get_current_user, RequireRole
│   │   ├── routes.py            #   GET /api/me
│   │   └── schemas.py           #   UserResponse schema
│   │
│   ├── orgs/                    # Organization management domain
│   │   ├── deps.py              #   get_current_org_membership, RequireOrgRole dependencies
│   │   ├── permissions.py       #   Permission assertion helpers (raise domain exceptions)
│   │   ├── routes.py            #   Member list, invite, role change, activate/deactivate
│   │   ├── schemas.py           #   Org-related Pydantic schemas
│   │   └── service.py           #   Member CRUD (pure database operations)
│   │
│   ├── admin/                   # System admin domain (SYSTEM_ADMIN only)
│   │   ├── routes_orgs.py       #   Org CRUD, ownership transfer, member introspection
│   │   ├── routes_users.py      #   User listing and deletion (DB + Cognito)
│   │   ├── schemas.py           #   Admin-specific schemas
│   │   └── service.py           #   System-admin database operations
│   │
│   ├── products/                # Products domain
│   │   ├── routes.py            #   Product CRUD + product-supplier link endpoints
│   │   ├── schemas.py           #   Product Pydantic schemas
│   │   └── service.py           #   Product data access
│   │
│   ├── suppliers/               # Suppliers domain
│   │   ├── routes.py            #   Supplier CRUD endpoints
│   │   ├── schemas.py           #   Supplier Pydantic schemas
│   │   └── service.py           #   Supplier data access
│   │
│   ├── users/                   # User lifecycle domain
│   │   └── service.py           #   get_or_create_user, placeholder claiming, deletion
│   │
│   ├── invites/                 # Invite orchestration domain
│   │   └── service.py           #   invite_user_to_org (coordinates Cognito + DB)
│   │
│   ├── bootstrap/               # Startup seeding
│   │   ├── seeder.py            #   run_bootstrap (idempotent admin + org creation)
│   │   └── seed_data.py         #   Example suppliers, products, and links
│   │
│   ├── health/                  # Health check
│   │   └── routes.py            #   GET /health
│   │
│   └── models/                  # SQLAlchemy ORM models
│       ├── base.py              #   Abstract base (UUID pk + created_at)
│       ├── user.py              #   User (cognito_sub, email, system_role)
│       ├── organization.py      #   Organization (name)
│       ├── org_membership.py    #   OrgMembership (user <-> org, role, active status)
│       ├── supplier.py          #   Supplier (org-scoped, contact info)
│       ├── product.py           #   Product (org-scoped, SKU, category)
│       └── product_supplier.py  #   ProductSupplier join table (is_active flag)
│
├── alembic/                     # Database migration infrastructure
│   ├── env.py                   #   Async migration runner (reads DATABASE_URL)
│   └── versions/                #   Auto-generated migration files
│
├── tests/                       # Test suite 1: mocked database (fast, no Postgres needed)
│   ├── conftest.py              #   App + httpx client fixtures
│   ├── unit/                    #   Pure logic tests (no HTTP, no real DB)
│   └── functional/              #   HTTP endpoint tests via async test client
│
├── testsv2/                     # Test suite 2: real database (transaction-per-test rollback)
│   ├── conftest.py              #   DB engine, session, transaction rollback fixtures
│   ├── factories.py             #   Factory functions that INSERT real rows
│   ├── integration/             #   Service-layer tests against real Postgres
│   └── functional/              #   HTTP endpoint tests against real Postgres
│       └── conftest.py          #   Auth bypass fixture (no Cognito needed in tests)
│
├── docs/                        # Documentation (you are here)
│   ├── getting-started.md       #   Setup and installation guide
│   ├── architecture.md          #   This file
│   ├── api-reference.md         #   All API endpoints
│   ├── developer-guide.md       #   Contributing, testing, coding standards
│   ├── deployment-guide.md      #   Production deployment
│   ├── troubleshooting.md       #   Common issues and fixes
│   └── cognito-setup.md         #   Cognito User Pool setup
│
├── Dockerfile                   # Dev Docker image (Python 3.11, Uvicorn)
├── Dockerfile.api               # Prod Docker image (Python 3.12, Gunicorn + Uvicorn)
├── docker-compose.yml           # Dev: API + Postgres
├── docker-compose.prod.yml      # Prod: API + Postgres + Web + Caddy (HTTPS)
├── Caddyfile                    # Caddy reverse proxy config (auto-HTTPS)
├── Makefile                     # Developer command shortcuts
├── build-and-push.sh            # Build + push Docker images to ECR
├── deploy.sh                    # Pull and restart on production server
├── requirements.txt             # Runtime Python dependencies
├── dev-requirements.txt         # Runtime + dev dependencies (includes tests, linting)
├── pyproject.toml               # Black config, pytest config, project metadata
├── mypy.ini                     # Type checking configuration
├── alembic.ini                  # Alembic migration config
├── run.py                       # Entry point: uvicorn app.main:app --reload
└── .env.example                 # Template for environment variables
```

---

## Domain Module Pattern

Every feature domain in the `app/` directory follows the same **3-file pattern**:

| File | Responsibility | Knows About |
|---|---|---|
| `routes.py` | HTTP endpoint definitions. Parses requests, wires auth dependencies, serializes responses. | HTTP, FastAPI, Pydantic schemas |
| `schemas.py` | Pydantic models for request bodies and response shapes. Handles validation and serialization. | Pydantic only |
| `service.py` | Pure database operations. Accepts a `db` session, returns ORM model instances. **Never raises HTTP exceptions.** | SQLAlchemy, ORM models, domain exceptions |

### Why this separation matters

- **Testability:** Service functions can be unit-tested with a mocked `db` session — no HTTP layer needed.
- **Reusability:** Services can be called from background jobs, CLI scripts, management commands, or other services without importing FastAPI.
- **Clarity:** Each file has a single responsibility. If you need to change how data is stored, you only touch `service.py`. If you need to change the API contract, you only touch `routes.py` and `schemas.py`.

### Dependency flow

```
routes.py  →  service.py  →  SQLAlchemy models
    ↓              ↓
schemas.py    exceptions.py
```

Routes depend on services and schemas. Services depend on models and exceptions. **Services never import from routes or schemas.**

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Caddy (Production only)                   │
│           Automatic HTTPS · Reverse Proxy                   │
│  <your-domain>        ->  web:3000  (frontend)              │
│  api.<your-domain>    ->  api:8000  (this API)              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │   FastAPI   │
                    │   (API)     │
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
   ┌─────▼─────┐   ┌──────▼──────┐   ┌──────▼───────┐
   │  AWS       │   │ PostgreSQL  │   │  CloudWatch  │
   │  Cognito   │   │   (DB)      │   │  (Logging)   │
   │  (Auth)    │   │             │   │              │
   └───────────┘   └─────────────┘   └──────────────┘
```

### Components

| Component | Role | Details |
|---|---|---|
| **FastAPI** | Web framework | Handles HTTP requests, routing, validation, serialization |
| **PostgreSQL 16** | Data storage | All application data — users, orgs, products, suppliers |
| **AWS Cognito** | Authentication | User sign-up/sign-in, JWT token issuance |
| **Caddy** | Reverse proxy (prod) | Automatic HTTPS via Let's Encrypt, routes traffic to API and frontend |
| **CloudWatch** | Logging (prod) | Centralized log aggregation via the `awslogs` Docker logging driver |

---

## Request Lifecycle

Here's what happens step-by-step when an HTTP request hits the API:

### 1. Middleware Layer

The `RequestLoggingMiddleware` (defined in `app/core/middleware.py`) intercepts every request:

- **Assigns a correlation ID** — Checks for an `X-Request-ID` header. If none exists, generates a UUID. This ID is included in all log messages for that request, making it easy to trace a single request through the logs.
- **Logs the request** — Method, path, and timing information.
- **Captures errors** — If the response is 4xx or 5xx, the middleware logs the response body for debugging.

### 2. CORS

FastAPI's `CORSMiddleware` validates the request's `Origin` header against the `CORS_ORIGINS` setting. Requests from unknown origins are rejected. This prevents unauthorized websites from calling the API.

### 3. Authentication

The `get_current_user` dependency (defined in `app/auth/deps.py`) runs on every authenticated endpoint:

1. Extracts the JWT from the `Authorization: Bearer <token>` header.
2. Fetches Cognito's public keys (JWKS) from `https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json`. The JWKS is **cached** after the first fetch (no network call on subsequent requests).
3. Validates the JWT: checks the signature, issuer, audience (`client_id`), and expiration.
4. Extracts the `sub` (Cognito user ID) and `email` from the token claims.
5. Looks up the user in the database by `cognito_sub`. If not found, creates a new `User` record (or claims an existing placeholder — see [Invite Flow](#placeholder-claiming)).

### 4. Organization Resolution

For org-scoped endpoints, the `get_current_org_membership` dependency (defined in `app/orgs/deps.py`) runs next:

1. Checks for an `X-Org-Id` header — if present, uses that org.
2. If no header, falls back to the user's **most recently joined active organization**.
3. Verifies the user has an **active** membership in that org.
4. Returns the `OrgMembership` object (which includes the user's role in this org).

### 5. Route Handler

The route function parses the request body using Pydantic schemas, calls the appropriate service function, and returns the result. The response is serialized automatically by FastAPI using the `response_model`.

### 6. Service Layer

Service functions execute database queries via SQLAlchemy. On validation or business rule failures, they raise **domain exceptions** (not HTTP exceptions).

### 7. Exception Handler

A custom exception handler in `app/main.py` catches all `AppError` subclasses and converts them to JSON HTTP responses with the appropriate status code.

### 8. Response

The JSON response is sent back to the client with headers including the `X-Request-ID` correlation ID.

---

## Multi-Tenancy

EasyInventory is a **multi-tenant** application. Every piece of business data (suppliers, products, product-supplier links) belongs to an **organization**. Users can be members of multiple organizations.

### How data isolation works

1. **Every business table has an `org_id` column** — a foreign key to the `organizations` table.
2. **Every service function receives an `org_id` parameter** — queries always include `WHERE org_id = :org_id`.
3. **The `org_id` comes from the authenticated user's org membership** — resolved by the `get_current_org_membership` dependency. It is **never** taken from the request body.

### Switching organizations

Users who belong to multiple orgs can switch between them by including the `X-Org-Id` header in their requests:

```
GET /api/products
Authorization: Bearer <token>
X-Org-Id: 550e8400-e29b-41d4-a716-446655440000
```

If the header is omitted, the API uses the user's most recently joined active org.

### Why this matters for developers

When writing new service functions, **always filter by `org_id`**. Never return data from one org to a user in another org. The org membership dependency already provides the correct `org_id` — just pass it through.

---

## Authentication (AWS Cognito)

The application uses **AWS Cognito** for user authentication. Users sign up and log in through Cognito, which issues JWT tokens. The API verifies these tokens on every authenticated request.

### Authentication flow

```
┌──────────┐     ┌──────────┐     ┌──────────────┐
│  Frontend │────>│  Cognito │────>│  Frontend    │
│  (Login)  │     │  (Auth)  │     │  (Has token) │
└──────────┘     └──────────┘     └──────┬───────┘
                                         │
                              Authorization: Bearer <jwt>
                                         │
                                  ┌──────▼───────┐
                                  │   API        │
                                  │  (Verifies)  │
                                  └──────────────┘
```

1. **User signs in** via the frontend (Cognito Hosted UI or SDK) and receives a JWT access token.
2. **Frontend sends requests** with the `Authorization: Bearer <token>` header.
3. **API verifies the token** by checking the JWT signature against Cognito's public keys (JWKS), and validating the issuer, audience, and expiration.
4. **User record is found or created** in the local database on first authenticated request.

### Key files

| File | What It Does | When It Runs |
|---|---|---|
| `app/auth/cognito_token.py` | Fetches JWKS, verifies JWT signature/claims | **Every authenticated request** (hot path) |
| `app/auth/cognito_admin.py` | Creates Cognito accounts for invitees, deletes users | Only during invite/delete operations (cold path) |
| `app/auth/deps.py` | FastAPI dependencies: `get_current_user`, `RequireRole` | Every authenticated endpoint |

### JWKS caching

The JWKS (JSON Web Key Set) is the set of public keys used to verify JWT signatures. The API fetches it once from Cognito on the first token verification, then caches it for the lifetime of the process. This means:

- No network call to Cognito on most requests — just local JWT verification.
- If Cognito rotates keys, restarting the API will fetch the new keys.

### Placeholder claiming

When a user is invited (before they have a Cognito account), a **placeholder** `User` record is created in the database with their email but no `cognito_sub`. When they sign up via Cognito and make their first API request:

1. The API sees a valid JWT with a `sub` and `email`.
2. It finds the placeholder user by email.
3. It "claims" the placeholder by setting the `cognito_sub` field.
4. All existing memberships (which were created during the invite) are activated.

### Setup

See [cognito-setup.md](cognito-setup.md) for the full Cognito User Pool configuration guide.

---

## Role-Based Access Control (RBAC)

The application has a **two-level role system** defined in `app/core/roles.py`.

### System Roles

Applied at the **user** level. Controls access to system-wide admin features.

| Role | Constant | Description |
|---|---|---|
| System Admin | `SystemRole.ADMIN` = `"SYSTEM_ADMIN"` | Can create organizations, manage all users, access `/api/admin/*` endpoints |
| System User | `SystemRole.USER` = `"SYSTEM_USER"` | Default role for all regular users |

### Organization Roles

Applied **per-organization** via the `org_memberships` table. Controls what a user can do within a specific organization.

| Role | Constant | Who Can Assign | Capabilities |
|---|---|---|---|
| Owner | `OrgRole.OWNER` = `"ORG_OWNER"` | System Admin only | Full control. Manage admins, employees, viewers. Cannot be demoted or removed. |
| Admin | `OrgRole.ADMIN` = `"ORG_ADMIN"` | Owner only | Invite members, manage employees and viewers. Cannot manage other admins or the owner. |
| Employee | `OrgRole.EMPLOYEE` = `"ORG_EMPLOYEE"` | Owner or Admin | View, create, and edit products and suppliers. Cannot delete resources or manage members. |
| Viewer | `OrgRole.VIEWER` = `"ORG_VIEWER"` | Owner or Admin | Read-only access to products and suppliers. |

### Permission rules

These rules are enforced in `app/orgs/permissions.py`:

- **Owner protection:** The org owner cannot be deactivated, removed, or have their role changed by anyone (including themselves). Ownership transfer requires a separate admin endpoint.
- **Admin hierarchy:** Only the owner can modify admins (change role, deactivate, remove). Admins cannot manage other admins — they can only manage employees and viewers.
- **Role assignment via invite:** Only `ORG_ADMIN`, `ORG_EMPLOYEE`, and `ORG_VIEWER` can be assigned during invite. `ORG_OWNER` requires ownership transfer.

### Role groups (convenience constants)

These are defined in `app/core/roles.py` and used throughout the codebase:

```python
OrgRole.ALL        = ("ORG_OWNER", "ORG_ADMIN", "ORG_EMPLOYEE", "ORG_VIEWER")
OrgRole.INVITABLE  = ("ORG_ADMIN", "ORG_EMPLOYEE", "ORG_VIEWER")
OrgRole.MANAGERS   = ("ORG_OWNER", "ORG_ADMIN")
```

### How roles are checked in routes

Routes use FastAPI dependency injection:

```python
# Any org member can access this endpoint
@router.get("/api/suppliers")
async def list_suppliers(
    membership: OrgMembership = Depends(get_current_org_membership),
    ...
)

# Only owners and admins can delete
@router.delete("/api/suppliers/{id}")
async def delete_supplier(
    membership: OrgMembership = Depends(RequireOrgRole("ORG_OWNER", "ORG_ADMIN")),
    ...
)
```

---

## Database & Models

### Technology stack

| Component | Technology | Purpose |
|---|---|---|
| Database | PostgreSQL 16 | Relational data storage |
| ORM | SQLAlchemy 2.0 (async) | Object-relational mapping |
| Driver | asyncpg | High-performance async Postgres driver |
| Migrations | Alembic | Schema version control |

### Database configuration

The database layer is defined in `app/core/database.py`:

- **`engine`** — Async SQLAlchemy engine created from the `DATABASE_URL` environment variable. When `DEBUG=true`, enables SQL query logging.
- **`async_session`** — Session factory with `expire_on_commit=False` (prevents lazy load errors after commit).
- **`get_db()`** — FastAPI dependency that yields a database session. Automatically commits on success and rolls back on error.

### Base model

All ORM models inherit from `BaseModel` (defined in `app/models/base.py`), which provides two common fields:

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | UUID | Auto-generated (`uuid4`) | Primary key |
| `created_at` | DateTime (with timezone) | Server-side `now()` | Record creation timestamp |

### Data models

```
┌──────────┐     ┌───────────────┐     ┌──────────────┐
│   User   │────<│ OrgMembership │>────│ Organization │
└──────────┘     └───────────────┘     └──────────────┘
                                              │
                              ┌───────────────┼───────────────┐
                              │               │               │
                        ┌─────▼────┐   ┌──────▼─────┐        │
                        │ Supplier │   │  Product   │        │
                        └─────┬────┘   └──────┬─────┘        │
                              │               │               │
                              └──────┐ ┌──────┘               │
                              ┌──────▼─▼──────┐               │
                              │ProductSupplier│               │
                              └───────────────┘               │
```

| Model | Table | Key Fields | Relations |
|---|---|---|---|
| `User` | `users` | `cognito_sub` (unique), `email`, `system_role`, `is_active` | → `OrgMembership` (one-to-many) |
| `Organization` | `organizations` | `name` | → `OrgMembership` (one-to-many) |
| `OrgMembership` | `org_memberships` | `org_id` (FK), `user_id` (FK), `org_role`, `is_active` | → `User`, `Organization` |
| `Supplier` | `suppliers` | `org_id` (FK), `name`, `contact_name`, `contact_email`, `contact_phone`, `notes` | — |
| `Product` | `products` | `org_id` (FK), `name`, `description`, `sku`, `category` | → `ProductSupplier` (one-to-many) |
| `ProductSupplier` | `product_suppliers` | `product_id` (FK), `supplier_id` (FK), `is_active` | → `Supplier` / Unique on `(product_id, supplier_id)` |

### Key design decisions

- **UUIDs as primary keys** — Every model uses UUIDs instead of auto-incrementing integers. This prevents ID enumeration attacks and makes it safe to expose IDs in URLs.
- **Org-scoping via foreign key** — Business data models (`Supplier`, `Product`) have an `org_id` foreign key. This is the foundation of multi-tenancy.
- **Soft state on memberships** — `OrgMembership.is_active` allows deactivating members without deleting their data. They can be reactivated later.
- **Join table with metadata** — `ProductSupplier` is not just a simple many-to-many join. It has an `is_active` flag, allowing you to deactivate a specific product-supplier relationship without removing it.

---

## Database Migrations (Alembic)

[Alembic](https://alembic.sqlalchemy.org/) manages database schema changes. Migration files live in `alembic/versions/`.

### Running migrations

```bash
# Via Docker (recommended)
docker compose exec api alembic upgrade head

# Via Makefile (local, with venv activated)
make migrate

# Windows (manual)
python -m alembic upgrade head
```

### Generating a new migration

After changing a model (adding a column, a new table, changing a constraint, etc.):

```bash
# Via Docker
docker compose exec api alembic revision --autogenerate -m "add category to products"

# Via Makefile (local)
make migrate-generate msg="add category to products"

# Windows
python -m alembic revision --autogenerate -m "add category to products"
```

**Always review the generated migration** before applying it. Alembic's autogenerate is good but not perfect — it may miss:
- Data migrations (populating new columns with default values)
- Index changes
- Enum value additions
- Complex constraint modifications

### Rolling back

```bash
# Rollback the last migration
docker compose exec api alembic downgrade -1

# Or via Makefile
make migrate-down

# Windows
python -m alembic downgrade -1
```

### Viewing history

```bash
docker compose exec api alembic history
```

### Connecting to the database directly

```bash
# Via Docker Compose
docker compose exec db psql -U postgres -d easyinventory

# Via Makefile
make db-shell
```

> **Important:** If you run Alembic locally (outside Docker), make sure `DATABASE_URL` points to `localhost`, not `db`. The `db` hostname only resolves inside the Docker network.

---

## Domain Exception System

The service layer and permission helpers raise **domain exceptions** instead of HTTP exceptions. A custom exception handler in `app/main.py` automatically converts them to JSON HTTP responses with the appropriate status code.

### Why?

- **Separation of concerns:** Services don't know about HTTP. They express business errors in business terms.
- **Testability:** You can test services without FastAPI — just catch the domain exceptions.
- **Consistency:** All error responses have the same shape: `{"detail": "error message"}`.

### Exception hierarchy

All exceptions inherit from `AppError` and are defined in `app/core/exceptions.py`:

```
AppError (400)                         # Base — catch-all for domain errors
├── NotAuthenticated (401)             # Missing or invalid credentials
├── InsufficientPermission (403)       # User lacks required role
│   ├── OwnerProtected (403)           # "Cannot {action} the organization owner"
│   └── AdminHierarchyViolation (403)  # "Only the owner can {action} an admin"
├── NotFound (404)                     # Resource does not exist
├── AlreadyExists (400)               # Duplicate resource
└── InvalidRole (400)                  # Invalid role value
```

### Usage in services

```python
from app.core.exceptions import NotFound, AlreadyExists

async def get_supplier(db: AsyncSession, supplier_id: UUID, org_id: UUID):
    supplier = await db.get(Supplier, supplier_id)
    if not supplier or supplier.org_id != org_id:
        raise NotFound("Supplier not found")
    return supplier

async def create_supplier(db: AsyncSession, org_id: UUID, name: str):
    if await supplier_name_exists(db, name, org_id):
        raise AlreadyExists("A supplier with that name already exists")
    # ... create the supplier
```

### What the client sees

```json
HTTP 404
{"detail": "Supplier not found"}
```

> **Rule:** Never raise `HTTPException` in the service layer. Always use domain exceptions from `app/core/exceptions.py`. The exception handler takes care of the HTTP mapping.

---

## Bootstrap & Seed Data

On every application startup, the **bootstrap seeder** (`app/bootstrap/seeder.py`) runs. It is fully **idempotent** — safe to run multiple times without creating duplicates.

### What it does

If `BOOTSTRAP_ADMIN_EMAIL` is configured in `.env`:

1. **Creates a user** with that email (as a placeholder if they haven't signed up via Cognito yet).
2. **Creates an organization** named per `BOOTSTRAP_ORG_NAME` (defaults to "Default Organization").
3. **Makes the user the `ORG_OWNER`** of that organization.
4. **Promotes the user to `SYSTEM_ADMIN`** system role.
5. **Seeds sample data** — suppliers, products, and product-supplier links (defined in `app/bootstrap/seed_data.py`).

### Sample seed data

| Type | Items |
|---|---|
| **Suppliers** | Fresh Farms Produce, Pacific Coast Seafood, Valley Grains Co., Mountain Spring Water |
| **Products** | Organic Apples, Whole Wheat Flour, Organic Oranges, Whole Milk, Brown Rice |
| **Links** | Various product-supplier connections |

### Becoming a System Admin

There are currently two ways to become a `SYSTEM_ADMIN`:

**1. Bootstrap (automatic):** Set `BOOTSTRAP_ADMIN_EMAIL` in `.env` to your email. On next startup, you'll be promoted.

**2. Manual database update:**

```bash
# Via Docker
docker compose exec db psql -U postgres -d easyinventory \
  -c "UPDATE users SET system_role = 'SYSTEM_ADMIN' WHERE email = 'admin@company.com';"
```

```powershell
# Windows (PowerShell) — all one line
docker compose exec db psql -U postgres -d easyinventory -c "UPDATE users SET system_role = 'SYSTEM_ADMIN' WHERE email = 'admin@company.com';"
```

---

## Related Guides

- [Getting Started](getting-started.md) — Installation and setup
- [API Reference](api-reference.md) — All endpoints and their parameters
- [Developer Guide](developer-guide.md) — Coding standards, testing, adding features
- [Deployment Guide](deployment-guide.md) — Production deployment
- [Troubleshooting](troubleshooting.md) — Common issues and fixes
