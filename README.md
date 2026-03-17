# EasyInventory API

FastAPI backend for the EasyInventory inventory management platform.

## Prerequisites

- [Git](https://git-scm.com/downloads) installed
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- [Python 3.11+](https://www.python.org/downloads/) (for local dev without Docker)

## Quick Start (Docker — Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/your-org/easyinventory-api.git
cd easyinventory-api

# 2. Create your environment file from the example
cp .env.example .env

# 3. Build and start all services (API + Postgres)
docker compose up --build

# 4. In a separate terminal, run database migrations
docker compose exec api alembic upgrade head

# 5. Verify everything is working
curl http://localhost:8000/health
# → {"status": "healthy", "service": "easyinventory-api"}
```

- **API:** http://localhost:8000
- **Swagger Docs:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

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


## Authentication (Cognito)
 
This app uses AWS Cognito for authentication. See
[docs/cognito-setup.md](docs/cognito-setup.md) for the full setup guide.
 
Required `.env` variables:
 
    COGNITO_REGION=us-east-1
    COGNITO_USER_POOL_ID=<your pool id>
    COGNITO_APP_CLIENT_ID=<your client id>
 
The app fetches Cognito's public keys (JWKS) on first token
verification and caches them for the process lifetime.

## Organization Management

> TODO roadmap item: [Multi-Organization Support User Story](docs/multi-org-support-user-story.md)

| Method | Endpoint | Role Required | Description |
|---|---|---|---|
| GET | /api/orgs/members | Any org member | List all members |
| POST | /api/orgs/invite | ORG_OWNER, ORG_ADMIN | Invite by email |
| PATCH | /api/orgs/members/{id}/role | ORG_OWNER, ORG_ADMIN | Change role |
| PATCH | /api/orgs/members/{id}/deactivate | ORG_OWNER, ORG_ADMIN | Deactivate |
| PATCH | /api/orgs/members/{id}/activate | ORG_OWNER, ORG_ADMIN | Reactivate |
| DELETE | /api/orgs/members/{id} | ORG_OWNER, ORG_ADMIN | Remove |

**Permission checks** are enforced in the route layer.
**Service layer** is pure database operations.

The owner cannot be deactivated, removed, or have their role changed.
Admins can manage employees and viewers but not other admins or the owner.

**Invite flow:** When inviting an email that hasn't signed up yet, a
placeholder user is created. When they sign up via Cognito, the
placeholder is automatically claimed and their membership activated.
Duplicate invites (active member or pending placeholder) return 400.

### Invite emails
When inviting a new email (not yet in the system), Cognito
automatically creates their account and sends an invite email
with a temporary password. The invite uses `admin_create_user`
via boto3.

Required in `.env`:
- `AWS_ACCESS_KEY_ID` — IAM user with CognitoPowerUser access
- `AWS_SECRET_ACCESS_KEY` — corresponding secret key

If the email already has a Cognito account, the invite only
creates the org membership (no duplicate Cognito account).

## Suppliers

| Method | Endpoint | Role Required | Description |
|---|---|---|---|
| GET | /api/suppliers | Any org member | List suppliers |
| GET | /api/suppliers/{id} | Any org member | Get supplier |
| POST | /api/suppliers | Any org member | Create supplier |
| PUT | /api/suppliers/{id} | Any org member | Update supplier |
| DELETE | /api/suppliers/{id} | ORG_OWNER, ORG_ADMIN | Delete supplier |

All supplier data is scoped to the current user's org. You can
only see and manage suppliers belonging to your organization.

## System Admin — Organization Management

| Method | Endpoint | Role Required | Description |
|---|---|---|---|
| POST | /api/admin/orgs | SYSTEM_ADMIN | Create org + assign owner |
| GET | /api/admin/orgs | SYSTEM_ADMIN | List all organizations |

**Onboarding a new client:**
1. System admin calls POST /api/admin/orgs with org name + owner email
2. If the email is new → Cognito invite sent, placeholder created
3. If the email exists → they become the active owner immediately
4. Owner logs in → can invite their own team members

**Becoming a system admin:**
Currently manual — update the `system_role` column in the database:
docker compose exec db psql -U postgres -d easyinventory \
-c "UPDATE users SET system_role = 'SYSTEM_ADMIN' WHERE email = 'admin@company.com';"
This will be replaced by a proper endpoint in a future sprint.

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

Use this if you want to run the API directly on your machine.
You still need PostgreSQL running (via Docker or installed locally).

```bash
# 1. Clone the repository (skip if already done)
git clone https://github.com/your-org/easyinventory-api.git
cd easyinventory-api

# 2. Create a Python virtual environment
python -m venv venv

# 3. Activate the virtual environment
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate          # Windows

# 4. Install all dependencies (app + dev tools)
pip install -r dev-requirements.txt

# 5. Create your environment file
cp .env.example .env

# 6. Update DATABASE_URL in .env to point to localhost (not "db")
#    DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/easyinventory

# 7. Start Postgres via Docker (if not already running)
docker run -d --name easyinventory-db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=easyinventory \
  -p 5432:5432 \
  postgres:16

# 8. Run database migrations
python -m alembic upgrade head

# 9. Start the development server
uvicorn app.main:app --reload

# 10. Verify everything is working
curl http://localhost:8000/health
# → {"status": "healthy", "service": "easyinventory-api"}
```

> **Tip:** Every time you open a new terminal, re-activate the virtual
> environment with `source venv/bin/activate` before running commands.

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


---
 
## Commit Message Convention
 
Use this format for every commit:
 
```
<type>: <short description>
 
Types:
  init  — project setup, scaffolding
  add   — new feature or file
  fix   — bug fix
  test  — adding or updating tests
  docs  — documentation only
  refactor — code change that doesn't add/fix
  chore — config, dependencies, CI
 
Examples:
  init: FastAPI project with folder structure
  add: User model with cognito_sub and system_role
  add: JWT validation middleware with 401/403 responses
  fix: duplicate user creation on concurrent first logins
  test: auth middleware returns 401 for expired tokens
  docs: Cognito User Pool setup instructions
```
 
---
 
## PR Review Checklist
 
Before approving any PR:
 
- [ ] Code runs locally (docker compose up, tests pass)
- [ ] No hardcoded secrets or credentials
- [ ] New env vars are documented in .env.example
- [ ] Database changes have an Alembic migration
- [ ] API changes include request/response schemas
- [ ] At least one test for new functionality
- [ ] PR description explains what and why