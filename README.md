# EasyInventory API

FastAPI backend for the EasyInventory inventory management platform — a multi-tenant, role-based inventory system with AWS Cognito authentication.

## Tech Stack

| Component | Technology |
|---|---|
| **Framework** | FastAPI (Python 3.11+) |
| **Database** | PostgreSQL 16 |
| **ORM** | SQLAlchemy 2.0 (async) + asyncpg |
| **Migrations** | Alembic |
| **Auth** | AWS Cognito (JWT) |
| **Validation** | Pydantic v2 |
| **Containers** | Docker / Docker Compose |
| **Reverse Proxy** | Caddy (auto-HTTPS) |
| **Prod Server** | Gunicorn + Uvicorn workers |
| **Code Quality** | Black (formatter) + mypy (type checker) |
| **Testing** | pytest + httpx (mocked DB) and pytest + real Postgres (transaction rollback) |

## Quick Start

```bash
git clone <repo-url>
cd easyinventory-api
cp .env.example .env        # Add your Cognito credentials
docker compose up --build    # API at http://localhost:8000
```

Interactive API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

## Documentation

| Guide | Description |
|---|---|
| [Getting Started](docs/getting-started.md) | Prerequisites, installation (Docker & local), environment variables |
| [Architecture](docs/architecture.md) | Project structure, request lifecycle, multi-tenancy, RBAC, database models |
| [API Reference](docs/api-reference.md) | All endpoints, request/response schemas, invite flow details |
| [Developer Guide](docs/developer-guide.md) | Contributing, testing (both suites), adding features, Makefile reference |
| [Deployment Guide](docs/deployment-guide.md) | Docker images, ECR, Caddy, production setup, deploy script |
| [Troubleshooting](docs/troubleshooting.md) | Common issues and fixes for dev, testing, and production |
| [Cognito Setup](docs/cognito-setup.md) | AWS Cognito User Pool configuration |

## Project Structure

```
app/
├── main.py              # App factory
├── core/                # Config, database, exceptions, middleware, roles
├── auth/                # Cognito JWT verification, auth dependencies
├── orgs/                # Organization membership management
├── admin/               # System admin endpoints
├── products/            # Product CRUD
├── suppliers/           # Supplier CRUD
├── invites/             # Invite orchestration (Cognito + DB)
├── users/               # User lifecycle
├── bootstrap/           # Startup seeding
├── health/              # Health check
└── models/              # SQLAlchemy ORM models
```

## Common Commands

| Command | Description |
|---|---|
| `make run` | Start dev server (Docker Compose) |
| `make test` | Run tests (mocked DB) |
| `make test-v2` | Run tests (real Postgres) |
| `make format` | Auto-format with Black |
| `make typecheck` | Run mypy type checking |
| `make migrate` | Apply database migrations |
| `make db-shell` | Open psql shell |

See the [Developer Guide](docs/developer-guide.md) for the full Makefile reference.
