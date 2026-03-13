.PHONY: run test lint format typecheck clean

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

lint: format typecheck

format:
	python -m black --check app/ tests/

format-fix:
	python -m black app/ tests/

typecheck:
	python -m mypy app/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +