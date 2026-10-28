# 주류 도매 온톨로지 + AI 에이전트

Palantir Foundry의 **온톨로지(object type / link type / action type / function)** 와
**제안-승인 방식 AI 에이전트**를 로컬에서 구현한 런타임입니다. 도메인은 한국 주류 도매
사업자의 영업·배송·기사 업무입니다.

- Foundry 계정 없이 동작하며, 스키마는 YAML이 단일 소스입니다.
- OSDK 호환 형태(`apiName`, `rid`, `primaryKey`, object set, `validate`/`apply`,
  `Idempotency-Key`, `X-Actor`)를 유지해 나중에 `@osdk/maker`로 내보내기 쉽습니다.

## 문서

- [구조 상세](구조상세.md) — 실행 경로, SchemaRegistry, 함수/액션 관계, 상태 전이,
  AI 에이전트의 역할, 스키마에서 생성되는 API·타입·문서·인덱스의 동작 방식
- [온톨로지 스키마](docs/domains/liquor/ontology.md) — 스키마에서 자동 생성되는 객체/링크/액션/함수/에이전트 요약

## 빠른 시작

```bash
docker compose up -d db          # PostgreSQL 16 (포트 55432)
uv sync
uv run alembic upgrade head
uv run ontology domains                              # 도메인 목록
uv run ontology --domain liquor schema validate
uv run ontology --domain liquor sync-indexes
uv run ontology --domain liquor seed --seed 42
uv run ontology export-web                           # 도메인별 클라이언트 + 랜딩 매니페스트
uv run uvicorn ontology_runtime.api.app:app --reload      # http://localhost:8000 (기본 도메인)
cd apps/web && pnpm install && pnpm dev                    # http://localhost:5173
```

`--domain`은 서브커맨드 앞뒤 어디에나 올 수 있고, 생략하면 `ONTOLOGY_DOMAIN`(기본 `liquor`)을
씁니다. 두 도메인을 동시에 띄울 때는 서로 다른 포트와 DB를 지정합니다.

```bash
ONTOLOGY_DOMAIN=bakery DATABASE_URL_BAKERY=postgresql+asyncpg://ontology:ontology@localhost:55432/ontology_bakery \
  uv run uvicorn ontology_runtime.api.app:app --port 8001
```

에이전트를 실제로 실행하려면 `OPENROUTER_API_KEY`가 필요합니다. 기본 테스트는 이 키 없이도
돌고, 실제 호출 테스트만 `-m live`로 분리되어 있습니다.

`uv run ontology --domain liquor demo`는 발주→배차→납품 시퀀스를 한 번에 재생하며,
`uv run ontology --domain liquor docs`는 스키마에서 `docs/domains/liquor/ontology.md`를 생성합니다.

## 구조

```
ontology/
  platform/             # 모든 도메인 공통 (ActionProposal/AgentRun, 제안 액션 3종)
  domains/
    liquor/             # 주류 도매 (16 object types, 25 links, 25 actions, 21 functions, 4 agents)
    bakery/             # 베이커리 유통 (격리 예시: 같은 이름의 Product를 다른 속성으로 정의)
src/ontology_runtime/
  loader.py registry.py # YAML → 메타모델 → 역링크/인덱스 도출 (도메인+플랫폼 병합)
  runtime.py            # 레지스트리 + 스토어 + 액션/함수 파사드
  db/                   # 엔진·세션·테이블 (JSONB objects/links, 감사 로그, 도메인별 엔진)
  store/                # JSONB 객체·링크 저장, 선언 인덱스 동기화
  query/                # allowlist 필터 DSL, object set, 집계
  validation/          # Violation 형태, 범용 객체 불변식
  actions/              # EditBatch 단일 쓰기 경로 (검증·감사·멱등성)
  functions/            # 함수 실행 레지스트리 (구현은 도메인 패키지에)
  agents/               # 에이전트 루프, 도구 표면, 가드레일, OpenRouter 어댑터
  api/                  # FastAPI (OSDK 형태)
  domains/
    liquor/             # 주류 도메인 함수·시드·데모
    bakery/             # 베이커리 도메인 함수·시드
  clientgen/            # TypeScript 클라이언트 + 웹 번들 생성
apps/web/               # React 운영 콘솔 (랜딩 + 도메인별 콘솔)
```

## 도메인 추가

도메인은 `ontology/domains/<name>/domain.yaml` 하나로 식별됩니다.

```yaml
apiName: bakery
displayName: 베이커리 유통
ridNamespace: bakery                       # rid 접두사: ri.bakery.object....
pythonPackage: ontology_runtime.domains.bakery
web:
  enabled: true
  order: 20
  tagline: 베이커리 생산·매장·배치 재고 콘솔
  apiBase: /api/bakery                     # Vite 프록시가 /api/bakery → /api 로 rewrite
  backendUrl: http://localhost:8001
```

1. `ontology/domains/<name>/` 에 object_types/·action_types/·link_types/·functions/·agents/ 작성
2. `uv run ontology --domain <name> schema validate`
3. `uv run ontology export-web` — 도메인 클라이언트 + 랜딩 매니페스트(`domains.json`) 생성
4. 끝. 전용 화면이 필요하면 `apps/web/src/domains/<name>/`에 페이지를 두고 `index.ts`의
   `extraNav` / `extraRoutes`에 등록합니다. 없으면 공통 콘솔(스키마·객체·인박스·채팅)로 동작합니다.

`ActionProposal` / `AgentRun` / 제안 액션 3종은 `ontology/platform/`에서 모든 도메인에
자동 병합되며, 도메인이 같은 이름을 재정의하면 스키마 로드가 실패합니다.

## 핵심 설계

**쓰기 경로는 하나.** 선언형 액션이든 함수 기반 액션이든 `EditBatch`를 만들고 단일
적용기가 반영합니다. `/validate`는 같은 파이프라인을 SAVEPOINT 안에서 실행하므로
`/apply`와 결과가 일치합니다.

**에이전트는 `apply` 도구를 갖지 않습니다.** 노출되는 도구는 `search_objects`,
`get_linked_objects`, `run_function`(읽기 전용), `validate_action`(dry-run),
`propose_action` 다섯 개뿐입니다. 프롬프트 인젝션으로도 무단 쓰기가 불가능합니다.

**제안 → 승인.** 에이전트가 만든 `ActionProposal`은 일반 온톨로지 객체입니다.
운영자가 승인하면 그때 `ActionService.apply()`가 기존 검증·감사 경로로 실행되고,
`action_runs`/`action_edits`에 승인자와 함께 기록됩니다.

**온톨로지가 UI 타입을 만든다.** `uv run ontology export-web`가 도메인별 TypeScript 타입·
클라이언트와 랜딩 매니페스트를 생성합니다. 속성/액션 추가 후 재생성만 하면 됩니다.

## 에이전트

| 에이전트 | 역할 | 제안 가능 액션 |
|---|---|---|
| `orderIntakeAgent` | 자유 텍스트 발주를 해석. 모호하면 되묻는다 | `CreateSalesOrder`, `SubmitSalesOrder` |
| `dispatchAgent` | 확정 발주와 가용 자원으로 배차 계획 | `PlanDeliveries`, `ReassignDriver`, `ReassignStop` |
| `exceptionAgent` | 결정적 탐지 결과를 원인별로 분류 | `ReassignStop`, `ReassignDriver`, `FailStop`, `CompleteStop` |
| `opsCopilotAgent` | 읽기 전용 분석·메시지 초안 | 없음 |

예외 탐지는 `detectDeliveryExceptions` 함수가 후보를 결정적으로 만들고 LLM이 판단합니다.
LLM이 문제를 발명하지 않게 해 재현성을 확보합니다.

모델 기본값은 `deepseek/deepseek-v4.1-flash-1017` (OpenRouter, 1M 컨텍스트, tool calling 지원).
에이전트별로 `model:`/`fallbackModel:`을 지정하거나, `OPENROUTER_MODEL`로 전역 변경할 수
있습니다. 어떤 모델을 썼는지는 `AgentRun.model`에 실행 단위로 기록됩니다.

```yaml
# ontology/domains/liquor/agents/opsCopilotAgent.yaml
apiName: opsCopilotAgent
model: anthropic/claude-opus-5-5
fallbackModel: deepseek/deepseek-v4.1-flash-1017
```

## API 예시

```bash
# 온톨로지 메타데이터
curl -s localhost:8000/api/ontology/objectTypes | jq '.data[].apiName'

# 객체 검색
curl -s -X POST localhost:8000/api/objectsets/SalesOrder/search \
  -H 'content-type: application/json' \
  -d '{"filter":{"field":"status","op":"eq","value":"confirmed"},"pageSize":5}' | jq

# 액션: 검증 → 적용 (멱등)
curl -s -X POST localhost:8000/api/actions/PlanDeliveries/validate \
  -H 'content-type: application/json' \
  -d '{"params":{"deliveryDate":"2026-10-27","depot":{"objectType":"Depot","rid":"..."}}}' | jq

curl -s -X POST localhost:8000/api/actions/PlanDeliveries/apply \
  -H 'content-type: application/json' -H 'Idempotency-Key: plan-1' -H 'X-Actor: dispatcher01' \
  -d '{"params":{"deliveryDate":"2026-10-27","depot":{"objectType":"Depot","rid":"..."}}}' | jq

# 에이전트 실행 → 제안 생성
curl -s -X POST localhost:8000/api/agents/orderIntakeAgent/invoke \
  -H 'content-type: application/json' -H 'X-Actor: rep01' \
  -d '{"input":"행복식당 한소주 360ml 4박스 내일 배송으로 접수해줘"}' | jq

# 인박스 확인 후 승인 (승인 시점에 실행)
curl -s localhost:8000/api/proposals?status=proposed | jq
curl -s -X POST localhost:8000/api/actions/ApproveActionProposal/apply \
  -H 'content-type: application/json' -H 'X-Actor: manager01' -H 'Idempotency-Key: approve-1' \
  -d '{"params":{"proposal":{"objectType":"ActionProposal","rid":"..."}}}' | jq
```

## 테스트

```bash
uv run pytest -q --cov=ontology_runtime --cov-fail-under=80   # 키 불필요 (fixture 리플레이)
uv run pytest -m live -q                                       # 실제 OpenRouter 호출 (키 필요)
```

통합 테스트는 PostgreSQL이 필요합니다. 기본값은 아래 환경변수로 재정의합니다.

| 변수 | 기본값 | 용도 |
|---|---|---|
| `ONTOLOGY_TEST_DATABASE_URL` | `.../ontology_test` | 통합 테스트 본문 |
| `ONTOLOGY_MIGRATION_DATABASE_URL` | `.../ontology_migrations` | up/down 마이그레이션 테스트 |
| `ONTOLOGY_API_DATABASE_URL` | `.../ontology_api` | API 테스트(모듈당 1회 시드) |
| `ONTOLOGY_KEEP_SEED` | 미설정 | `1`이면 API 테스트 후 시드 데이터 유지 |

`-m live` 테스트는 기본 실행에서 제외됩니다(`addopts = -m 'not live'`).

## v1 범위 밖

면허 규제 강제, 재고·공병 보증금, 미수금/수금, 인증(정적 역할 맵만), value type,
interface(YAML 키만 예약), 집합 연산, 스트리밍 구독, 객체 단위 권한, 멀티테넌시,
OSDK 내보내기, 지오코딩/OSRM, 에이전트 자율 실행.
