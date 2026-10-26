# Project Instructions

## What This Is

A local, Palantir-Foundry-style **ontology runtime** for a Korean liquor wholesale
business: object/link/action/function meta-model, a single validated write path,
and a propose→approve AI agent workflow. Korean is used for domain copy and docs;
code identifiers are English.

## Tech Stack

- Python 3.13, `uv` (never pip/venv directly)
- FastAPI + Pydantic v2, SQLAlchemy 2 async + asyncpg, Alembic
- PostgreSQL 16 (JSONB object/link store), port `55432` via Docker
- pytest / pytest-asyncio, ruff, mypy (strict)
- Frontend: React 18 + Vite 5 + TypeScript (strict), TanStack Query, React Router, pnpm

## Commands

- DB up: `docker compose up -d db`
- Sync deps: `uv sync`
- Migrate: `uv run alembic upgrade head`
- Validate schema: `uv run ontology schema validate`
- Seed: `uv run ontology seed --seed 42`
- Run API: `uv run uvicorn ontology_runtime.api.app:app --reload`
- Run web: `cd apps/web && pnpm dev`
- Unit tests: `uv run pytest tests/unit tests/test_version.py -q`
- All tests (needs DB): `uv run pytest -q`
- Coverage gate: `uv run pytest -q --cov=ontology_runtime --cov-fail-under=80`
- Live LLM tests (needs key): `uv run pytest -m live -q`
- Lint: `uv run ruff check . && uv run ruff format --check . && uv run mypy src`

`make test` / `make lint` / `make migrate` / `make seed` wrap the above.

## Project Structure

- `ontology/schema/` — **source of truth**: object_types/, action_types/ (one file each),
  plus `link_types.yaml`, `functions.yaml`, `interfaces.yaml`, `agents/`, `prompts/`
- `src/ontology_runtime/` — loader → registry → runtime facade; `db/`, `store/`,
  `query/`, `validation/`, `actions/`, `functions/`, `agents/`, `api/`, `seed/`, `clientgen/`
- `apps/web/` — React ops console; `src/generated/` is generated, never hand-edit
- `migrations/` — Alembic; one core migration
- `tests/` — `unit/` (no DB), `integration/` (PostgreSQL), `live/` (opt-in LLM), `e2e/`
- `docs/ontology.md` — generated from the schema

## Conventions

- **YAML first.** Add/change object types, actions, links, functions, agents in
  `ontology/schema/`, then regenerate: `uv run ontology export-client --out apps/web/src/generated`
  and `uv run ontology docs`. Never hand-edit generated TS or `docs/ontology.md`.
- YAML/JSON keys are camelCase (`apiName`, `displayName`, `fromObjectType`); Python
  modules/functions are snake_case; classes PascalCase; test files `test_*.py`.
- **One write path.** Every action (declarative or function-backed) builds an
  `EditBatch` applied by `ActionService`. `/validate` runs the same pipeline as a dry run.
  Do not add a second persistence path.
- **Agents cannot write.** The tool surface is `search_objects`, `get_linked_objects`,
  `run_function` (read only), `validate_action`, `propose_action`. Keep it that way.
- Errors: typed `OntologyError` subclasses in `errors.py`, mapped to one API envelope
  `{success, data, error, meta}` and a shared `Violation` shape.
- Queries: only the allowlisted filter DSL in `query/filter.py`; never interpolate
  user field names/operators into SQL.
- Mutable state lives in PostgreSQL; `EditContext` provides a read-your-writes overlay
  for validation. Prefer new objects over mutation, as in the existing code.
- Some imports are function-local on purpose to break `context ↔ store ↔ actions`
  cycles (ruff `PLC0415` is ignored). Keep that pattern rather than introducing cycles.
- Date/timestamp indexes intentionally use ISO text expressions (`properties->>'x'`);
  temporal casts are not IMMUTABLE in PostgreSQL.

## Testing Notes

- Integration tests auto-create their databases (`ontology_test`, `ontology_migrations`,
  `ontology_api`) against the Docker Postgres. A running DB is required.
- `pytest` excludes `live` by default (`addopts = -m 'not live'`). Never make default
  tests require `OPENROUTER_API_KEY`; use `tests/fixtures/llm/fake_provider.py`.
- TDD is expected: write a failing test, implement, keep coverage ≥ 80%.

## Security

- `.env` holds `DATABASE_URL` and `OPENROUTER_API_KEY`; never commit or print it.
- Authorization is a static role map (`X-Actor` / `X-Role`); there is no auth provider in v1.
