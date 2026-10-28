DOMAIN ?= liquor

.PHONY: db-up db-down migrate seed web test lint domains gen-web

db-up:
	docker compose up -d db

db-down:
	docker compose down

migrate:
	uv run alembic upgrade head

domains:
	uv run ontology domains

seed:
	uv run ontology --domain $(DOMAIN) seed --seed 42

gen-web:
	uv run ontology export-web
	uv run ontology --domain $(DOMAIN) docs

web:
	cd apps/web && pnpm dev

test:
	uv run pytest -q

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src
