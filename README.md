# EasyInventory API
 
FastAPI backend for the EasyInventory inventory management platform.
 
## Prerequisites
 
- Docker and Docker Compose
- Python 3.11+ (for local dev without Docker)
 
## Quick Start
 
1. Clone the repo
2. `cp .env.example .env`
3. `docker compose up --build`
4. API: http://localhost:8000
5. Docs: http://localhost:8000/docs
 
## Development Commands
 
| Command            | What it does                           |
|--------------------|----------------------------------------|
| `make run`         | Start the app with Docker              |
| `make build`       | Rebuild and start                      |
| `make test`        | Run all tests                          |
| `make test-unit`   | Run unit tests only                    |
| `make test-functional` | Run functional tests only          |
| `make lint`        | Check formatting (black) + types (mypy)|
| `make format-fix`  | Auto-fix formatting with black         |
| `make typecheck`   | Run mypy type checks                   |
 
## Local Dev Without Docker
 
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r dev-requirements.txt
uvicorn app.main:app --reload
```
 
## Project Structure
 
```
app/
├── main.py          # App factory + CORS + router registration
├── core/
│   └── config.py    # Environment-based settings (pydantic)
├── api/routes/      # Route handlers (one file per feature)
├── models/          # SQLAlchemy models (PR-02+)
├── schemas/         # Pydantic request/response schemas
└── services/        # Business logic layer
tests/
├── conftest.py      # Shared fixtures (app, client)
├── unit/            # Pure logic tests (no HTTP)
└── functional/      # HTTP endpoint tests
```

 
 
## Verification Before Opening the PR
 
Run these locally before pushing:
 
```bash
# 1. App starts and serves requests
docker compose up --build -d
curl http://localhost:8000/health
# → {"status":"healthy","service":"easyinventory-api"}
 
# 2. All tests pass
make test
# → 8 passed
 
# 3. Formatting is clean
make format-fix
make lint
# → All checks passed, 0 errors
 
# 4. Swagger UI loads
open http://localhost:8000/docs
```
 
If all four pass, push and open the PR.
 
---
 
## PR Description Template for This PR
 
```
## What
Backend project scaffold with FastAPI, Docker, tooling, and tests.
 
## Why
Foundation for all Sprint 1 backend work. Establishes project
structure, dev workflow, and quality gates.
 
## How to test
1. `cp .env.example .env`
2. `docker compose up --build`
3. `curl http://localhost:8000/health` → 200
4. `make test` → 8 passed
5. `make lint` → no errors
 
## Checklist
- [x] `make test` passes
- [x] `make lint` passes (black + mypy)
- [x] No hardcoded secrets
- [x] .env.example documents all vars
- [x] README has setup instructions
```