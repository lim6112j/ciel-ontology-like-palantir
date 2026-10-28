#!/usr/bin/env bash
# liquor 도메인 API 실행 (포트 8000, DB: DATABASE_URL 또는 기본 ontology)
set -euo pipefail
cd "$(dirname "$0")"

export ONTOLOGY_DOMAIN="${ONTOLOGY_DOMAIN:-liquor}"
export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://ontology:ontology@localhost:55432/ontology}"

exec uv run uvicorn ontology_runtime.api.app:app --reload --port 8000
