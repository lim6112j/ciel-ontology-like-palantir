#!/usr/bin/env bash
# makgeolli 도메인 API 실행 (포트 8002, DB: ontology_makgeolli)
#
# 첫 실행이면 전용 DB 생성 → 마이그레이션 → 인덱스 → 빈 DB일 때만 시드까지 한다.
# alembic은 DATABASE_URL_MAKGEOLLI 오버라이드를 읽지 않고 기본 DATABASE_URL만 보므로
# 마이그레이션 단계에서만 DATABASE_URL을 makgeolli DB로 덮어쓴다.
set -euo pipefail
cd "$(dirname "$0")"

MAKGEOLLI_DB_NAME="${MAKGEOLLI_DB_NAME:-ontology_makgeolli}"
export ONTOLOGY_DOMAIN=makgeolli
export DATABASE_URL_MAKGEOLLI="${DATABASE_URL_MAKGEOLLI:-postgresql+asyncpg://ontology:ontology@localhost:55432/$MAKGEOLLI_DB_NAME}"

# 1) 전용 DB가 없으면 생성 (최초 1회)
if ! docker exec ontology-db psql -U ontology -tAc \
  "SELECT 1 FROM pg_database WHERE datname = '$MAKGEOLLI_DB_NAME'" | grep -q 1; then
  docker exec ontology-db createdb -U ontology "$MAKGEOLLI_DB_NAME"
  echo "🆕 makgeolli 전용 DB 생성: $MAKGEOLLI_DB_NAME"
fi

# 2) 마이그레이션 (멱등: 이미 head면 no-op). 스키마는 도메인별 테이블이 없어 공통이다.
DATABASE_URL="$DATABASE_URL_MAKGEOLLI" uv run alembic upgrade head

# 3) 선언 인덱스 동기화
uv run ontology --domain makgeolli sync-indexes

# 4) 빈 DB일 때만 시드. seed는 기존 데이터를 truncate하므로 데이터가 있으면 건너뛴다.
ROW_COUNT="$(docker exec ontology-db psql -U ontology -d "$MAKGEOLLI_DB_NAME" -tAc \
  "SELECT count(*) FROM objects")"
if [ "$ROW_COUNT" = "0" ]; then
  uv run ontology --domain makgeolli seed --seed 42
fi

exec uv run uvicorn ontology_runtime.api.app:app --port 8002
