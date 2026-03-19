.PHONY: run test test-v2 test-db test-db-stop lint format format-check format-fix typecheck clean

# Use venv python if available, fall back to python3
PYTHON := $(shell [ -x venv/bin/python ] && echo venv/bin/python || echo python3)

run:
	docker compose up

build:
	docker compose up --build

test:
	$(PYTHON) -m pytest tests/ -v

test-unit:
	$(PYTHON) -m pytest tests/unit/ -v

test-functional:
	$(PYTHON) -m pytest tests/functional/ -v

test-db:
	@docker rm -f easyinventory-test-db 2>/dev/null || true
	docker run -d --name easyinventory-test-db \
	  -e POSTGRES_USER=test \
	  -e POSTGRES_PASSWORD=test \
	  -e POSTGRES_DB=easyinventory_test \
	  -p 5433:5432 \
	  postgres:16-alpine
	@echo "Waiting for Postgres to become ready..."
	@max_retries=30; \
	  until docker exec easyinventory-test-db pg_isready -U test -d easyinventory_test -q >/dev/null 2>&1; do \
	    if [ $$max_retries -le 0 ]; then \
	      echo "Postgres did not become ready in time. Please check the container logs (docker logs easyinventory-test-db)." >&2; \
	      exit 1; \
	    fi; \
	    max_retries=$$((max_retries - 1)); \
	    echo "Postgres is not ready yet; retrying..."; \
	    sleep 1; \
	  done


test-db-stop:
	docker rm -f easyinventory-test-db 2>/dev/null || true

TEST_DB_URL = postgresql+asyncpg://test:test@localhost:5433/easyinventory_test

test-v2:
	DATABASE_URL=$(TEST_DB_URL) $(PYTHON) -m alembic upgrade head
	DATABASE_URL=$(TEST_DB_URL) $(PYTHON) -m pytest testsv2/ -v

lint: format-check typecheck

format:
	$(PYTHON) -m black app/ tests/ testsv2/

format-check:
	$(PYTHON) -m black --check app/ tests/ testsv2/

format-fix: format

typecheck:
	$(PYTHON) -m mypy app/

migrate:
	$(PYTHON) -m alembic upgrade head

migrate-generate:
	$(PYTHON) -m alembic revision --autogenerate -m "$(msg)"

migrate-down:
	$(PYTHON) -m alembic downgrade -1

db-shell:
	docker compose exec db psql -U postgres -d easyinventory
	
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +