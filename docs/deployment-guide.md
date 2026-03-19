# Deployment Guide

How to deploy the EasyInventory API to production using Docker, AWS ECR, and Caddy for automatic HTTPS.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Docker Images](#docker-images)
- [Production Environment Variables](#production-environment-variables)
- [Build & Push to ECR](#build--push-to-ecr)
- [Server Setup](#server-setup)
- [Deploy Script](#deploy-script)
- [Caddy Configuration](#caddy-configuration)
- [Database in Production](#database-in-production)
- [Logging (CloudWatch)](#logging-cloudwatch)
- [Manual Operations](#manual-operations)
- [Rollback](#rollback)

---

## Architecture Overview

The production setup runs **four Docker containers** behind Caddy for automatic HTTPS:

```
              Internet
                 │
        ┌────────▼────────┐
        │     Caddy        │  ← Automatic HTTPS (Let's Encrypt)
        │     :80 / :443   │
        └─┬────────────┬──┘
          │            │
   <your-domain>  api.<your-domain>
          │            │
    ┌─────▼─────┐  ┌──▼──────────────────────┐
    │   Web     │  │   API                    │
    │   :3000   │  │   :8000                  │
    │ (frontend)│  │   Gunicorn + Uvicorn     │
    └───────────┘  │   2 async workers        │
                   └──────────┬───────────────┘
                              │
                    ┌─────────▼──────────┐
                    │   PostgreSQL 16    │
                    │   :5432 (local)    │
                    └────────────────────┘
```

| Service | Image | Description |
|---|---|---|
| **db** | `postgres:16-alpine` | PostgreSQL database with persistent volume |
| **api** | `<aws-account-id>.dkr.ecr.<region>.amazonaws.com/easyinventory/api:latest` | FastAPI + Gunicorn (2 workers) |
| **web** | `<aws-account-id>.dkr.ecr.<region>.amazonaws.com/easyinventory/web:latest` | Frontend application |
| **caddy** | `caddy:2-alpine` | Reverse proxy with auto-HTTPS |

---

## Docker Images

The project has **two Dockerfiles** — one for development, one for production:

| File | Python | Server | Use Case |
|---|---|---|---|
| `Dockerfile` | 3.11-slim | Uvicorn (single process) | Local development |
| `Dockerfile.api` | 3.12-slim | Gunicorn + Uvicorn workers | Production |

### Production Dockerfile details

```dockerfile
# Dockerfile.api — production image
FROM python:3.12-slim
WORKDIR /app

# asyncpg needs system libraries for Postgres
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn uvicorn
COPY . .

EXPOSE 8000
CMD ["gunicorn", "app.main:app", \
     "-w", "2", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
```

**Key differences from dev:**
- Python 3.12 (latest stable) instead of 3.11
- Installs `gcc` and `libpq-dev` for asyncpg compilation
- Gunicorn with 2 Uvicorn workers (handles concurrent requests via multiple processes)
- Access and error logs written to stdout (captured by Docker logging)

---

## Production Environment Variables

Create a `.env.prod` file on your server with the following variables:

### Required

| Variable | Example | Description |
|---|---|---|
| `DB_USER` | `postgres` | PostgreSQL username |
| `DB_PASSWORD` | `<strong-password>` | PostgreSQL password |
| `DB_NAME` | `easyinventory` | Database name |
| `AWS_REGION` | `us-east-1` | AWS region for ECR and CloudWatch |
| `AWS_ACCOUNT_ID` | `123456789012` | Your AWS account ID |
| `COGNITO_REGION` | `us-east-2` | Region of your Cognito User Pool |
| `COGNITO_USER_POOL_ID` | `us-east-2_XXXXXXXXX` | Cognito User Pool ID |
| `COGNITO_APP_CLIENT_ID` | `4bjjm8t2...` | Cognito App Client ID |
| `CORS_ORIGINS` | `https://<your-domain>` | Allowed CORS origins (comma-separated) |

### Optional

| Variable | Default | Description |
|---|---|---|
| `BOOTSTRAP_ADMIN_EMAIL` | — | Email to auto-promote as SYSTEM_ADMIN on boot |
| `BOOTSTRAP_ORG_NAME` | `"Default Organization"` | Name of the auto-created org |
| `DEBUG` | `false` | Enable SQL query logging (never true in prod) |

### Example `.env.prod`

```bash
DB_USER=postgres
DB_PASSWORD=your-strong-password-here
DB_NAME=easyinventory
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012
COGNITO_REGION=us-east-2
COGNITO_USER_POOL_ID=us-east-2_XXXXXXXXX
COGNITO_APP_CLIENT_ID=your-client-id
CORS_ORIGINS=https://<your-domain>
BOOTSTRAP_ADMIN_EMAIL=admin@example.com
```

> **Security:** Never commit `.env.prod` to git. Add it to `.gitignore`.

---

## Build & Push to ECR

The `build-and-push.sh` script builds Docker images for both the API and the frontend, then pushes them to AWS ECR.

### Prerequisites

1. **AWS CLI** installed and configured with permissions for ECR.
2. **Docker** installed and running.
3. **ECR repositories created:**
   - `easyinventory/api`
   - `easyinventory/web`
4. **`AWS_ACCOUNT_ID` environment variable set.**

### Creating ECR repositories (first time only)

```bash
aws ecr create-repository --repository-name easyinventory/api --region us-east-1
aws ecr create-repository --repository-name easyinventory/web --region us-east-1
```

### Running the build

```bash
export AWS_ACCOUNT_ID=123456789012
./build-and-push.sh
```

**What the script does:**

1. Logs into ECR using `aws ecr get-login-password`.
2. Builds the API image from `Dockerfile.api` (targeting `linux/amd64`).
3. Tags and pushes the API image to ECR.
4. Builds the frontend image from the sibling `easyinventory-web/` directory.
5. Tags and pushes the web image to ECR.

> **Important:** The script builds for `linux/amd64`. If your dev machine is Apple Silicon (ARM), Docker will cross-compile. This is slower but produces images compatible with most cloud servers.

---

## Server Setup

### Initial setup (first deployment)

1. **Provision a server** (EC2, DigitalOcean, etc.) running Ubuntu or Amazon Linux.

2. **Install Docker and Docker Compose:**

   ```bash
   # Ubuntu
   sudo apt-get update
   sudo apt-get install -y docker.io docker-compose-plugin
   sudo usermod -aG docker $USER
   # Log out and back in for group change to take effect
   ```

3. **Install AWS CLI:**

   ```bash
   curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
   unzip awscliv2.zip
   sudo ./aws/install
   aws configure  # Enter your credentials
   ```

4. **Clone the repo** (or just copy the necessary files):

   ```bash
   git clone <your-repo-url>
   cd easyinventory-api
   ```

5. **Create `.env.prod`** with your production values (see above).

6. **Update the Caddyfile** with your actual domain:

   ```
   <your-domain> {
       reverse_proxy web:3000
   }

   api.<your-domain> {
       reverse_proxy api:8000
   }
   ```

7. **Point your DNS** — Create A records for `<your-domain>` and `api.<your-domain>` pointing to your server's IP.

8. **Run the first deployment:**

   ```bash
   # Login to ECR
   aws ecr get-login-password --region us-east-1 | \
     docker login --username AWS --password-stdin \
     <aws-account-id>.dkr.ecr.us-east-1.amazonaws.com

   # Pull images and start all services
   docker compose --env-file .env.prod -f docker-compose.prod.yml pull
   docker compose --env-file .env.prod -f docker-compose.prod.yml up -d

   # Run database migrations
   docker compose --env-file .env.prod -f docker-compose.prod.yml exec api alembic upgrade head
   ```

9. **Verify:** Open `https://<your-domain>` — Caddy will automatically obtain a TLS certificate.

---

## Deploy Script

For subsequent deployments after the initial setup, use the `deploy.sh` script:

```bash
./deploy.sh
```

**What the script does:**

1. Sources `.env.prod` for AWS credentials.
2. Logs into ECR.
3. Pulls the latest `api` image.
4. Restarts the `api` container with `docker compose up -d api`.
5. Runs `alembic upgrade head` to apply any pending database migrations.
6. Prunes dangling Docker images to free disk space.

### Full deployment workflow

```bash
# On your dev machine: build and push new images
export AWS_ACCOUNT_ID=123456789012
./build-and-push.sh

# On the server: pull and deploy
ssh your-server
cd easyinventory-api
./deploy.sh
```

---

## Caddy Configuration

The `Caddyfile` configures Caddy as a reverse proxy with automatic HTTPS:

```
<your-domain> {
    reverse_proxy web:3000
}

api.<your-domain> {
    reverse_proxy api:8000
}
```

### How it works

- Caddy automatically obtains and renews TLS certificates from Let's Encrypt.
- HTTP (port 80) is automatically redirected to HTTPS (port 443).
- The `web` and `api` hostnames resolve to their Docker containers via Docker's internal DNS.

### Caddy volumes

The production `docker-compose.prod.yml` mounts two volumes for Caddy:

| Volume | Purpose |
|---|---|
| `caddy_data` | Stores TLS certificates and ACME data |
| `caddy_config` | Stores auto-generated Caddy config |

> **Important:** Don't delete these volumes — if you do, Caddy will need to re-obtain certificates from Let's Encrypt (which has rate limits).

---

## Database in Production

### Persistent storage

PostgreSQL data is stored in a Docker volume (`pgdata`). This persists across container restarts.

### Running migrations

Migrations run automatically as part of `deploy.sh`. To run them manually:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml exec api alembic upgrade head
```

### Database backups

The production setup does not include automated backups. You should set up periodic backups:

```bash
# Manual backup
docker compose --env-file .env.prod -f docker-compose.prod.yml exec db \
  pg_dump -U postgres easyinventory > backup_$(date +%Y%m%d).sql

# Restore from backup
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T db \
  psql -U postgres easyinventory < backup_20240115.sql
```

Consider using a cron job or AWS RDS for automated backups in production.

### Connecting to the database

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml exec db \
  psql -U postgres -d easyinventory
```

> **Note:** The database port (`5432`) is bound to `127.0.0.1` in production — it is not accessible from outside the server.

---

## Logging (CloudWatch)

All four services use the `awslogs` Docker logging driver to send logs to **AWS CloudWatch**:

| Service | Log Group | Log Stream |
|---|---|---|
| db | `/easyinventory/db` | `db` |
| api | `/easyinventory/api` | `api` |
| web | `/easyinventory/web` | `web` |
| caddy | `/easyinventory/caddy` | `caddy` |

### Prerequisites

- The EC2 instance (or server) must have an **IAM role** with `CloudWatchLogsFullAccess` permissions, or you must configure the AWS credentials on the server.
- Log groups are created automatically (`awslogs-create-group: "true"`).

### Viewing logs

```bash
# Via AWS CLI
aws logs tail /easyinventory/api --follow

# Or view in the AWS Console:
# CloudWatch → Log groups → /easyinventory/api
```

### Local Docker logs (fallback)

If CloudWatch is not configured, you can still view logs locally:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f api
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f db
```

---

## Manual Operations

### Restart a single service

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml restart api
```

### Restart all services

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml down
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

### View running containers

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```

### Shell into the API container

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml exec api /bin/bash
```

### Promote a System Admin

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml exec db \
  psql -U postgres -d easyinventory \
  -c "UPDATE users SET system_role = 'SYSTEM_ADMIN' WHERE email = 'admin@example.com';"
```

---

## Rollback

If a deployment breaks something, you can rollback to the previous image:

### Quick rollback (restart with cached image)

If the old image is still cached on the server:

```bash
# List available local images
docker images | grep easyinventory

# Tag the previous image as latest
docker tag <previous-image-id> \
  <aws-account-id>.dkr.ecr.<region>.amazonaws.com/easyinventory/api:latest

# Restart the container
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d api
```

### Rollback via ECR

If you need to pull an older image:

1. Check available tags in ECR (AWS Console or CLI).
2. Update `docker-compose.prod.yml` to use a specific tag instead of `latest`.
3. Pull and restart.

### Database migration rollback

If a migration caused issues:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml exec api alembic downgrade -1
```

> **Tip:** Always take a database backup before deploying migrations that modify existing data.

---

## Related Guides

- [Getting Started](getting-started.md) — Local development setup
- [Architecture](architecture.md) — System design and components
- [Developer Guide](developer-guide.md) — Contributing and testing
- [Troubleshooting](troubleshooting.md) — Common issues and fixes
