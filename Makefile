.PHONY: run test test-v2 test-db test-db-stop lint format format-check format-fix typecheck clean

run:
	docker compose up

build:
	docker compose up --build

test:
	python -m pytest tests/ -v

test-unit:
	python -m pytest tests/unit/ -v

test-functional:
	python -m pytest tests/functional/ -v

test-db:
	@docker rm -f easyinventory-test-db 2>/dev/null || true
	docker run -d --name easyinventory-test-db \
	  -e POSTGRES_USER=test \
	  -e POSTGRES_PASSWORD=test \
	  -e POSTGRES_DB=easyinventory_test \
	  -p 5433:5432 \
	  postgres:16-alpine
	@echo "Waiting for Postgres…"
	@sleep 2


test-db-stop:
	docker rm -f easyinventory-test-db 2>/dev/null || true

TEST_DB_URL = postgresql+asyncpg://test:test@localhost:5433/easyinventory_test

test-v2:
	DATABASE_URL=$(TEST_DB_URL) alembic upgrade head
	DATABASE_URL=$(TEST_DB_URL) python -m pytest testsv2/ -v

lint: format-check typecheck

format:
	python -m black app/ tests/ testsv2/

format-check:
	python -m black --check app/ tests/ testsv2/

format-fix: format

typecheck:
	python -m mypy app/

migrate:
	alembic upgrade head

migrate-generate:
	alembic revision --autogenerate -m "$(msg)"

migrate-down:
	alembic downgrade -1

db-shell:
	docker compose exec db psql -U postgres -d easyinventory
	
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +