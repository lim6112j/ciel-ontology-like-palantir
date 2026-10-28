#!/usr/bin/env bash
# bakery 도메인 API 실행 (포트 8001, DB: ontology_bakery)
#
# 첫 실행이면 전용 DB 생성 → 마이그레이션 → 인덱스 → 빈 DB일 때만 시드까지 한다.
# alembic은 DATABASE_URL_BAKERY 오버라이드를 읽지 않고 기본 DATABASE_URL만 보므로
# 마이그레이션 단계에서만 DATABASE_URL을 bakery DB로 덮어쓴다.
set -euo pipefail
cd "$(dirname "$0")"

BAKERY_DB_NAME="${BAKERY_DB_NAME:-ontology_bakery}"
export ONTOLOGY_DOMAIN=bakery
export DATABASE_URL_BAKERY="${DATABASE_URL_BAKERY:-postgresql+asyncpg://ontology:ontology@localhost:55432/$BAKERY_DB_NAME}"

# 1) 전용 DB가 없으면 생성 (최초 1회)
if ! docker exec ontology-db psql -U ontology -tAc \
  "SELECT 1 FROM pg_database WHERE datname = '$BAKERY_DB_NAME'" | grep -q 1; then
  docker exec ontology-db createdb -U ontology "$BAKERY_DB_NAME"
  echo "🆕 bakery 전용 DB 생성: $BAKERY_DB_NAME"
fi

# 2) 마이그레이션 (멱등: 이미 head면 no-op). 스키마는 도메인별 테이블이 없어 공통이다.
DATABASE_URL="$DATABASE_URL_BAKERY" uv run alembic upgrade head

# 3) 선언 인덱스 동기화
uv run ontology --domain bakery sync-indexes

# 4) 빈 DB일 때만 시드. seed는 기존 데이터를 truncate하므로 데이터가 있으면 건너뛴다.
ROW_COUNT="$(docker exec ontology-db psql -U ontology -d "$BAKERY_DB_NAME" -tAc \
  "SELECT count(*) FROM objects")"
if [ "$ROW_COUNT" = "0" ]; then
  uv run ontology --domain bakery seed --seed 42
fi

exec uv run uvicorn ontology_runtime.api.app:app --port 8001
