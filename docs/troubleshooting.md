# Troubleshooting

Solutions for common issues you may encounter when developing, testing, or deploying the EasyInventory API.

---

## Table of Contents

- [Docker & Startup Issues](#docker--startup-issues)
- [Database Issues](#database-issues)
- [Authentication Issues](#authentication-issues)
- [Testing Issues](#testing-issues)
- [API Runtime Errors](#api-runtime-errors)
- [Deployment Issues](#deployment-issues)
- [Code Quality Issues](#code-quality-issues)

---

## Docker & Startup Issues

### Container exits immediately / `db` container not ready

**Symptom:** `docker compose up` starts but the API container restarts or fails to connect to the database.

**Cause:** The API starts before PostgreSQL is ready to accept connections.

**Fix:**

```bash
# Stop everything
docker compose down

# Start the database first and wait for it
docker compose up db -d
sleep 5

# Then start the API
docker compose up api
```

Or simply re-run `docker compose up` — Docker will restart the API automatically once the database is ready (`restart: always` in production).

---

### Port 5432 already in use

**Symptom:** `Error: bind: address already in use` when starting Docker Compose.

**Cause:** Another PostgreSQL instance (or another Docker container) is using port 5432.

**Fix:**

```bash
# Find what's using the port
# macOS / Linux
lsof -i :5432

# Stop it, or change the port in docker-compose.yml:
# ports:
#   - "5433:5432"

# Then update DATABASE_URL to use port 5433:
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/easyinventory
```

```powershell
# Windows
netstat -aon | findstr :5432
# Kill the process or change the port as described above
```

---

### Port 8000 already in use

**Symptom:** API won't start, port conflict error.

**Fix:**

```bash
# macOS / Linux: find and kill the process
lsof -i :8000
kill <PID>

# Or change the API port in docker-compose.yml
```

---

### Docker Compose mounts not reflecting code changes

**Symptom:** You edit a file but the running API doesn't pick up the change.

**Cause:** Volume mounts only work in the dev `docker-compose.yml`. The production compose file uses baked-in images.

**Fix (dev):** The dev `docker-compose.yml` mounts `.:/app`, so changes should reflect immediately with Uvicorn's `--reload`. If not:

```bash
docker compose restart api
```

---

## Database Issues

### `alembic upgrade head` fails with "relation already exists"

**Symptom:** Migration error saying a table or column already exists.

**Cause:** The database state is out of sync with the Alembic migration history — typically from manually creating tables or running `Base.metadata.create_all`.

**Fix:**

```bash
# Check the current migration state
docker compose exec api alembic current

# If empty or wrong, stamp the database to the current head
docker compose exec api alembic stamp head

# If a specific migration is the problem, stamp to that revision
docker compose exec api alembic stamp <revision_id>
```

---

### "Connection refused" when running Alembic locally

**Symptom:** `alembic upgrade head` fails with `Connection refused` when running outside Docker.

**Cause:** Your `DATABASE_URL` uses `db` as the hostname (the Docker service name), which only resolves inside the Docker network.

**Fix:** When running Alembic locally, use `localhost`:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/easyinventory \
  python -m alembic upgrade head
```

Or make sure the database container's port is exposed (it is by default in `docker-compose.yml`).

---

### "Role 'postgres' does not exist" or auth errors

**Cause:** The Postgres container was created with different credentials than what you're using.

**Fix:**

```bash
# Remove the volume and recreate (WARNING: deletes all data)
docker compose down -v
docker compose up
```

---

### Data from another org visible / org isolation broken

**Cause:** A service function is missing the `WHERE org_id = :org_id` filter.

**Fix:** Every business query **must** filter by `org_id`. Check the service function and add the filter. See [Architecture: Multi-Tenancy](architecture.md#multi-tenancy).

---

## Authentication Issues

### `401 Unauthorized` on every request

**Possible causes:**

1. **Token expired** — Cognito tokens expire after 1 hour by default. Get a new token.

2. **Wrong Cognito environment variables:**
   ```bash
   # Verify your .env file has the correct values
   COGNITO_REGION=us-east-2
   COGNITO_USER_POOL_ID=us-east-2_XXXXXXXXX
   COGNITO_APP_CLIENT_ID=your-client-id-here
   ```

3. **Token from wrong User Pool** — If you have multiple Cognito pools (dev, staging, prod), make sure your token matches the pool configured in `.env`.

4. **Malformed Authorization header** — Must be exactly `Authorization: Bearer <token>` (note the space after "Bearer").

---

### `403 Forbidden` — "Insufficient permission"

**Cause:** Your user or org role doesn't have the required permission for the endpoint.

**Debug:**

```bash
# Check your system role
curl -s http://localhost:8000/api/me \
  -H "Authorization: Bearer <token>" | python -m json.tool

# Check your org role
curl -s http://localhost:8000/api/orgs/me \
  -H "Authorization: Bearer <token>" | python -m json.tool
```

See [Architecture: RBAC](architecture.md#role-based-access-control-rbac) for the full permission matrix.

---

### Cognito `AdminCreateUser` fails during invite

**Possible causes:**

1. **Missing AWS credentials** — The API needs AWS credentials with `cognito-idp:AdminCreateUser` permission.
2. **Wrong region or pool ID** — Double-check `COGNITO_REGION` and `COGNITO_USER_POOL_ID`.
3. **Email already exists in Cognito** — The invite flow handles this gracefully, but check the Cognito console if you see unexpected errors.

---

### JWKS fetch fails on API startup

**Symptom:** First authenticated request takes a long time or times out.

**Cause:** The API can't reach Cognito's JWKS endpoint.

**Fix:**
- Check internet connectivity from the server/container.
- Verify the JWKS URL: `https://cognito-idp.<region>.amazonaws.com/<pool-id>/.well-known/jwks.json`
- Make sure `COGNITO_REGION` and `COGNITO_USER_POOL_ID` are correct.

---

## Testing Issues

### Suite 1 (`tests/`): "app already started" or fixture errors

**Fix:** Make sure you're not running the dev server while running tests. Alternatively, clear caches:

```bash
make clean
make test
```

---

### Suite 2 (`testsv2/`): "CONNECTION_REFUSED" or database errors

**Cause:** The test database container isn't running.

**Fix:**

```bash
# Start the test database first
make test-db

# Wait a few seconds for it to be ready, then run tests
make test-v2
```

---

### Suite 2: "Refusing to run tests against a non-test database"

**Cause:** Safety check — `DATABASE_URL` doesn't contain the word "test".

**Fix:** Use the `make test-v2` command which sets the correct `DATABASE_URL` automatically. If running manually:

```bash
DATABASE_URL=postgresql+asyncpg://test:test@localhost:5433/easyinventory_test \
  python -m pytest testsv2/ -v
```

---

### Suite 2: Tests fail with "table does not exist"

**Cause:** Migrations haven't been run on the test database.

**Fix:** `make test-v2` runs migrations automatically. If running manually:

```bash
DATABASE_URL=postgresql+asyncpg://test:test@localhost:5433/easyinventory_test \
  python -m alembic upgrade head
```

---

### Tests pass locally but fail in CI

**Common causes:**

1. **Missing environment variables** — Make sure CI sets all required vars.
2. **Database not available** — CI needs a Postgres service or container.
3. **Port conflicts** — Make sure the test database port (5433) is available.
4. **Cache issues** — Run `make clean` before tests in CI.

---

## API Runtime Errors

### `422 Unprocessable Entity`

**Cause:** Pydantic validation failed. The request body doesn't match the expected schema.

**Debug:** Read the response body — it contains details about which field failed:

```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

**Common mistakes:**
- Missing required fields
- Wrong data types (string instead of UUID, integer instead of string)
- Invalid email format
- UUID formatted incorrectly

---

### `409 Conflict` when linking supplier to product

**Cause:** The supplier is already linked to this product.

**Fix:** Check existing links before adding:

```bash
curl -s http://localhost:8000/api/products/<product-id>/suppliers \
  -H "Authorization: Bearer <token>" | python -m json.tool
```

If the link exists but is inactive, update it instead of creating a new one:

```bash
curl -s -X PATCH http://localhost:8000/api/products/<product-id>/suppliers/<supplier-id> \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"is_active": true}'
```

---

### `500 Internal Server Error`

**Debug:** Check the API logs for the full traceback:

```bash
# Docker dev
docker compose logs -f api

# Docker prod
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f api
```

Look for the `X-Request-ID` header in the error response — it can be used to find the specific request in CloudWatch logs.

---

## Deployment Issues

### ECR push fails with "no basic auth credentials"

**Fix:** Re-authenticate with ECR:

```bash
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  <aws-account-id>.dkr.ecr.us-east-1.amazonaws.com
```

ECR tokens expire after 12 hours.

---

### `deploy.sh` fails with "Missing .env.prod"

**Fix:** Make sure `.env.prod` exists in the same directory as `deploy.sh`:

```bash
ls -la .env.prod
```

---

### Caddy shows "connection refused" for API

**Cause:** The API container isn't running or hasn't started yet.

**Fix:**

```bash
# Check container status
docker compose --env-file .env.prod -f docker-compose.prod.yml ps

# Check API logs
docker compose --env-file .env.prod -f docker-compose.prod.yml logs api
```

---

### Caddy can't get SSL certificate

**Possible causes:**

1. **DNS not pointed** — A records for your domain and `api.` subdomain must point to your server's IP.
2. **Ports 80/443 blocked** — Firewall must allow inbound HTTP and HTTPS traffic.
3. **Rate limited** — Let's Encrypt has [rate limits](https://letsencrypt.org/docs/rate-limits/). Wait and try again.

---

### CloudWatch logs not appearing

**Possible causes:**

1. **IAM permissions** — Server needs `CloudWatchLogsFullAccess` or equivalent.
2. **AWS credentials** — Must be configured on the server (`aws configure` or instance role).
3. **Region mismatch** — `AWS_REGION` in `.env.prod` must match where you expect to see logs.

---

## Code Quality Issues

### Black formatting check fails

```bash
# See which files need formatting
python -m black --check --diff app/ tests/ testsv2/

# Auto-fix
make format
```

---

### mypy type errors

```bash
# Run mypy to see all errors
make typecheck

# Common fixes:
# - Add return type annotations to functions
# - Add parameter type annotations
# - Use Optional[str] instead of str | None for Python 3.9 compat
```

All functions in `app/` must have type annotations. Tests are exempt.

---

## Still Stuck?

1. **Check the logs** — most issues are visible in the API or database logs.
2. **Check the interactive docs** — visit `http://localhost:8000/docs` to test endpoints directly.
3. **Clear everything and start fresh:**

   ```bash
   docker compose down -v
   make clean
   docker compose up --build
   docker compose exec api alembic upgrade head
   ```

---

## Related Guides

- [Getting Started](getting-started.md) — Setup and installation
- [Architecture](architecture.md) — How the system works
- [Developer Guide](developer-guide.md) — Testing and coding standards
- [Deployment Guide](deployment-guide.md) — Production setup
