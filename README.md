# easyinventory-api# EasyInventory API

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
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

## Project Structure