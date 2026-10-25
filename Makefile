.PHONY: db-up db-down migrate seed web test lint

db-up:
	docker compose up -d db

db-down:
	docker compose down

migrate:
	uv run alembic upgrade head

seed:
	uv run ontology seed --seed 42

web:
	cd apps/web && pnpm dev

test:
	uv run pytest -q

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src
