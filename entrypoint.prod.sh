#!/bin/sh
set -e

echo "Waiting for database..."
while ! python -c "
import asyncio, asyncpg, os, re
url = os.environ['DATABASE_URL']
# Convert SQLAlchemy URL to asyncpg format
url = re.sub(r'^postgresql\+asyncpg://', 'postgresql://', url)
asyncio.run(asyncpg.connect(url))
" 2>/dev/null; do
  echo "  DB not ready, retrying in 2s..."
  sleep 2
done
echo "Database is ready"

echo "Running database migrations..."
alembic upgrade head

echo "Starting application..."
exec "$@"
