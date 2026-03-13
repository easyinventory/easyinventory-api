# EasyInventory API

FastAPI backend for the EasyInventory inventory management platform.

## Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local dev without Docker)

## Quick Start

1. Clone the repo
2. `cp .env.example .env`
3. `docker compose up --build`
4. Run migrations: `docker compose exec api alembic upgrade head`
5. API: http://localhost:8000
6. Docs: http://localhost:8000/docs

## Health Check

```
GET http://localhost:8000/health
→ {"status": "healthy", "service": "easyinventory-api"}
```

## Development Commands

| Command              | What it does                            |
|----------------------|-----------------------------------------|
| `make run`           | Start the app with Docker               |
| `make build`         | Rebuild and start                       |
| `make test`          | Run all tests                           |
| `make test-unit`     | Run unit tests only                     |
| `make test-functional` | Run functional tests only             |
| `make lint`          | Check formatting (black) + types (mypy) |
| `make format-fix`    | Auto-fix formatting with black          |
| `make typecheck`     | Run mypy type checks                    |

## Database

| Command | What it does |
|---|---|
| `make migrate` | Run all pending migrations |
| `make migrate-generate msg="description"` | Generate a new migration |
| `make migrate-down` | Rollback last migration |
| `make db-shell` | Open psql shell |

**Important:** Always run database commands through Docker, not locally:

```bash
# Run migrations
docker compose exec api alembic upgrade head

# Generate a new migration
docker compose exec api alembic revision --autogenerate -m "description"

# Rollback last migration
docker compose exec api alembic downgrade -1

# View migration history
docker compose exec api alembic history

# Connect to the database directly
docker compose exec db psql -U postgres -d easyinventory
```

Running Alembic locally will fail because `db` (the Postgres hostname)
only resolves inside the Docker network.

## Local Dev Without Docker

If you prefer running the API directly on your machine (Postgres must
still be running via Docker or locally):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# Update DATABASE_URL in .env to use localhost instead of db
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/easyinventory

uvicorn app.main:app --reload
```

## Project Structure

```
app/
├── main.py              # App factory, CORS, lifespan DB check
├── core/
│   ├── config.py        # Environment-based settings (pydantic)
│   └── database.py      # SQLAlchemy engine, session, get_db dependency
├── api/routes/          # Route handlers (one file per feature)
├── models/
│   ├── base.py          # Abstract base model (UUID pk + created_at)
│   ├── user.py          # User model (cognito_sub, system_role)
│   ├── organization.py  # Organization model
│   └── org_membership.py # Org membership with role + FKs
├── schemas/             # Pydantic request/response schemas
└── services/            # Business logic layer
alembic/
├── env.py               # Async migration runner
└── versions/            # Migration files (auto-generated)
tests/
├── conftest.py          # Shared fixtures (app, async client)
├── unit/                # Pure logic tests (no HTTP, no DB)
└── functional/          # HTTP endpoint tests via test client
```

## Environment Variables

See `.env.example` for all required variables. Key ones:

| Variable | Used In | Description |
|---|---|---|
| `DATABASE_URL` | PR-02 | Postgres connection string |
| `COGNITO_REGION` | PR-03 | AWS region for Cognito |
| `COGNITO_USER_POOL_ID` | PR-03 | Cognito User Pool ID |
| `COGNITO_APP_CLIENT_ID` | PR-03 | Cognito App Client ID |
| `BOOTSTRAP_ADMIN_EMAIL` | PR-06 | Email to auto-promote to SYSTEM_ADMIN |

## Branch Workflow

```
feature branch (S1-XX/description)
  → PR into dev (during sprint)
    → PR into main (end of sprint, after testing)
```

All PRs require 1 approval + passing CI (black, mypy, pytest).