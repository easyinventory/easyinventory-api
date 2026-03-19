# Getting Started

This guide walks you through setting up the EasyInventory API on your local machine. Choose between Docker (recommended — zero configuration) or running Python directly.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start — Docker (Recommended)](#quick-start--docker-recommended)
- [Quick Start — Local Dev Without Docker](#quick-start--local-dev-without-docker)
- [Environment Variables](#environment-variables)
- [Next Steps](#next-steps)

---

## Prerequisites

Before you begin, make sure you have the following tools installed on your machine.

### Git

Git is the version control system we use to manage our code.

- **macOS:** Git comes pre-installed. Verify with `git --version`. If missing, install via [Homebrew](https://brew.sh/): `brew install git`
- **Windows:** Download from [git-scm.com](https://git-scm.com/downloads). During installation, choose "Git from the command line and also from 3rd-party software."

### Docker Desktop

Docker lets you run the entire application (API + database) in isolated containers — no need to install PostgreSQL or Python manually.

- **macOS:** Download from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)
- **Windows:** Download from the same link. Requires WSL 2 (the installer will prompt you to enable it).

After installing, **make sure Docker Desktop is running** (you should see the whale icon in your system tray / menu bar).

### Python 3.11+ (for local dev without Docker)

If you want to run the API directly on your machine (without Docker), you need Python 3.11 or newer.

- **macOS:** `brew install python@3.11` or download from [python.org](https://www.python.org/downloads/)
- **Windows:** Download from [python.org](https://www.python.org/downloads/). **Important:** Check the "Add Python to PATH" box during installation.

Verify your installation:

```bash
# macOS / Linux
python3 --version

# Windows (Command Prompt or PowerShell)
python --version
```

### AWS CLI (optional)

Only needed if you are deploying to production or testing Cognito invite flows locally. Install from [aws.amazon.com/cli](https://aws.amazon.com/cli/).

---

## Quick Start — Docker (Recommended)

This is the fastest way to get the API running. Docker handles Python, PostgreSQL, and all dependencies for you.

### 1. Clone the repository

```bash
# Same on macOS, Linux, and Windows
git clone https://github.com/your-org/easyinventory-api.git
cd easyinventory-api
```

### 2. Create your environment file

The `.env` file holds configuration values (database URL, Cognito settings, etc.). We provide a template:

```bash
# macOS / Linux
cp .env.example .env

# Windows (Command Prompt)
copy .env.example .env

# Windows (PowerShell)
Copy-Item .env.example .env
```

Open `.env` in your editor and fill in any required values. For local development, the defaults work out of the box — the Docker Compose setup overrides `DATABASE_URL` automatically. See [Environment Variables](#environment-variables) below for details on each setting.

### 3. Build and start all services

```bash
# Same on all platforms
docker compose up --build
```

This starts two containers:

| Container | What it is | Port |
|-----------|-----------|------|
| **api** | FastAPI application (Uvicorn) | `localhost:8000` |
| **db** | PostgreSQL 16 | `localhost:5432` |

The API code is mounted as a volume, so any file changes you make are reflected immediately without rebuilding.

> **Tip:** Add `-d` to run in detached mode (background): `docker compose up --build -d`

### 4. Run database migrations

In a **separate terminal** (while the containers are running):

```bash
# Same on all platforms
docker compose exec api alembic upgrade head
```

This creates all the database tables. You only need to do this once, or whenever new migrations are added by the team.

### 5. Verify everything is working

```bash
# macOS / Linux
curl http://localhost:8000/health

# Windows (PowerShell)
Invoke-WebRequest -Uri http://localhost:8000/health | Select-Object -ExpandProperty Content

# Windows (Command Prompt)
curl http://localhost:8000/health
```

Expected response:

```json
{"status": "healthy", "service": "easyinventory-api"}
```

### You're up and running!

- **API:** http://localhost:8000
- **Swagger Docs (interactive):** http://localhost:8000/docs — try out endpoints directly in the browser
- **ReDoc (readable):** http://localhost:8000/redoc — clean, searchable API documentation

### Stopping the application

```bash
# Stop all containers (preserves data)
docker compose down

# Stop and remove ALL data (database wiped clean)
docker compose down -v
```

### Rebuilding after dependency changes

If someone adds a new Python package to `requirements.txt`, rebuild:

```bash
docker compose up --build
```

---

## Quick Start — Local Dev Without Docker

Use this approach if you prefer running the Python API directly on your machine. You still need PostgreSQL — the easiest way is to run just the database in Docker.

### 1. Clone the repository

```bash
git clone https://github.com/your-org/easyinventory-api.git
cd easyinventory-api
```

### 2. Create a Python virtual environment

A virtual environment (venv) is an isolated Python installation for this project. It keeps your system Python clean and prevents package conflicts between different projects on your machine.

```bash
# macOS / Linux
python3 -m venv venv

# Windows
python -m venv venv
```

### 3. Activate the virtual environment

You need to activate the venv **every time you open a new terminal** before running any project commands.

```bash
# macOS / Linux
source venv/bin/activate

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Windows (Command Prompt)
venv\Scripts\activate.bat
```

You will know it's active when you see `(venv)` at the start of your terminal prompt.

### 4. Install dependencies

```bash
# Same on all platforms (with venv activated)
pip install -r dev-requirements.txt
```

This installs all runtime dependencies **plus** dev tools (pytest, black, mypy, httpx). If you only need runtime deps, use `requirements.txt` instead — but for development you want the full set.

### 5. Create your environment file

```bash
# macOS / Linux
cp .env.example .env

# Windows (Command Prompt)
copy .env.example .env

# Windows (PowerShell)
Copy-Item .env.example .env
```

### 6. Update DATABASE_URL for localhost

When running outside Docker, the database hostname is `localhost` instead of `db`. Open `.env` and change the `DATABASE_URL` line:

```dotenv
# Change this (Docker internal hostname):
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/easyinventory

# To this (localhost):
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/easyinventory
```

> **Why?** Inside Docker, services talk to each other using container names (`db`). Outside Docker, the database is accessed via `localhost`.

### 7. Start PostgreSQL via Docker

Even if you're running the API locally, the easiest way to get PostgreSQL is through Docker:

```bash
# macOS / Linux
docker run -d --name easyinventory-db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=easyinventory \
  -p 5432:5432 \
  postgres:16
```

```powershell
# Windows (PowerShell) — all one line
docker run -d --name easyinventory-db -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=easyinventory -p 5432:5432 postgres:16
```

To check it's running: `docker ps` — you should see a `postgres:16` container.

### 8. Run database migrations

```bash
# macOS / Linux
python3 -m alembic upgrade head

# Windows
python -m alembic upgrade head
```

### 9. Start the development server

```bash
# macOS / Linux
python3 run.py

# Windows
python run.py
```

Or equivalently:

```bash
uvicorn app.main:app --reload
```

The `--reload` flag makes the server restart automatically when you change code. You'll see output like:

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using WatchFiles
```

### 10. Verify everything is working

```bash
# macOS / Linux
curl http://localhost:8000/health

# Windows (PowerShell)
Invoke-WebRequest -Uri http://localhost:8000/health | Select-Object -ExpandProperty Content
```

Expected: `{"status": "healthy", "service": "easyinventory-api"}`

---

## Environment Variables

All configuration is loaded from a `.env` file using [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/). The settings class is defined in `app/core/config.py`.

### Required Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | — | PostgreSQL async connection string. Format: `postgresql+asyncpg://user:password@host:port/dbname` |
| `COGNITO_REGION` | — | AWS region where your Cognito User Pool lives (e.g., `us-east-1`) |
| `COGNITO_USER_POOL_ID` | — | Cognito User Pool ID (e.g., `us-east-1_AbC123`) |
| `COGNITO_APP_CLIENT_ID` | — | Cognito App Client ID |

### Optional Variables

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `EZInventory API` | Application name shown in Swagger docs title |
| `DEBUG` | `false` | When `true`, SQLAlchemy logs every SQL query to the console. **Never enable in production.** |
| `AWS_ACCESS_KEY_ID` | — | IAM credentials for Cognito admin operations (sending invite emails, deleting users). Not needed if you are only testing with mocked auth. |
| `AWS_SECRET_ACCESS_KEY` | — | Corresponding IAM secret key |
| `BOOTSTRAP_ADMIN_EMAIL` | — | If set, creates a bootstrap admin user + default organization on every startup. See [Architecture Guide — Bootstrap & Seed Data](architecture.md#bootstrap--seed-data). |
| `BOOTSTRAP_ORG_NAME` | `Default Organization` | Name for the bootstrap organization |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated list of allowed CORS origins (e.g., `http://localhost:5173,https://your-app.com`) |

### Docker vs Local — DATABASE_URL

When using Docker Compose, the `DATABASE_URL` is automatically overridden in `docker-compose.yml`:

```
postgresql+asyncpg://postgres:postgres@db:5432/easyinventory
```

The hostname `db` resolves to the PostgreSQL container inside the Docker network. When running locally (outside Docker), use `localhost` instead:

```
postgresql+asyncpg://postgres:postgres@localhost:5432/easyinventory
```

### Cognito Setup

For full Cognito User Pool configuration instructions, see [cognito-setup.md](cognito-setup.md).

---

## Next Steps

Now that you have the API running:

- **Understand the system:** Read the [Architecture Guide](architecture.md) to learn how the codebase is organized, how auth works, and how data flows through the system.
- **Explore the API:** Check the [API Reference](api-reference.md) for all available endpoints and their parameters.
- **Start developing:** Read the [Developer Guide](developer-guide.md) for coding standards, testing, and a full walkthrough of adding new features.
- **Deploy to production:** See the [Deployment Guide](deployment-guide.md) when you're ready to ship.
- **Fix issues:** Check [Troubleshooting](troubleshooting.md) if something isn't working.
