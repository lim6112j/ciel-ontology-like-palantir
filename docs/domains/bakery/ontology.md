# 온톨로지 스키마

생성일: 2026-10-28

## 오브젝트 타입

### ActionProposal — 액션제안

에이전트가 제안한 액션. 운영자 승인 전에는 어떤 객체도 변경되지 않는다.

- 기본키: `proposalNo`
- 상태머신: proposed→approved, proposed→rejected, proposed→expired, approved→failed

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| proposalNo (제안번호) | string | O |  |
| actionType (액션) | string | O | O |
| params (파라미터) | json | O |  |
| rationale (제안근거) | text | O |  |
| confidence (신뢰도) | decimal |  |  |
| status (상태) | enum | O | O |
| violations (사전검증결과) | json |  |  |
| targetObjectType (대상타입) | string |  | O |
| targetRid (대상객체) | string |  | O |
| agentRunRid (에이전트실행) | objectRef |  | O |
| approvedBy (승인자) | string |  |  |
| approvedAt (승인시각) | timestamp |  |  |
| decidedAt (결정시각) | timestamp |  |  |
| resultingRunId (실행기록ID) | string |  |  |
| feedbackNote (피드백) | text |  |  |

링크: `agentRun` → AgentRun

### AgentRun — 에이전트실행

에이전트 호출 1건의 감사 기록. 도구 호출과 토큰 사용량을 보관한다.

- 기본키: `runNo`

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| runNo (실행번호) | string | O |  |
| agentApiName (에이전트) | string | O | O |
| model (모델) | string | O |  |
| inputText (입력) | text | O |  |
| toolCallCount (도구호출수) | integer | O |  |
| inputTokens (입력토큰) | integer |  |  |
| outputTokens (출력토큰) | integer |  |  |
| latencyMs (소요(ms)) | integer |  |  |
| status (상태) | enum | O | O |
| error (오류) | text |  |  |
| transcript (대화기록) | json |  |  |

링크: `proposals` → ActionProposal

### Batch — 생산배치

한 번의 생산 실행. 제품·수량·생산일·소비기한을 기록한다.

- 기본키: `batchNo`
- 상태머신: planned→baked, baked→shipped, baked→wasted, planned→wasted

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| batchNo (배치번호) | string | O |  |
| productRid (제품) | objectRef | O | O |
| producedOn (생산일) | date | O | O |
| expiresOn (소비기한) | date | O | O |
| quantity (생산수량) | integer | O |  |
| status (상태) | enum | O | O |

링크: `product` → Product, `store` → Store

### Product — 제품

베이커리 SKU. 주류 도메인의 Product와 이름은 같지만 속성은 완전히 다르다.

- 기본키: `sku`

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| sku (SKU) | string | O |  |
| name (제품명) | string | O | O |
| category (분류) | enum | O | O |
| shelfLifeDays (유통기한(일)) | integer | O |  |
| unitPrice (단가(원)) | integer | O |  |
| active (판매중) | boolean | O | O |

링크: `batches` → Batch

### Store — 매장

베이커리 제품을 판매하는 매장.

- 기본키: `storeNo`
- 상태머신: active→closed, closed→active

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| storeNo (매장번호) | string | O |  |
| name (매장명) | string | O | O |
| status (상태) | enum | O | O |
| openedOn (개점일) | date |  |  |

링크: `batches` → Batch

## 액션 타입

- **ApproveActionProposal** (제안 승인, 함수 기반) — 운영자가 제안을 승인하면 대상 액션이 동일한 검증·감사 경로로 실행된다. 운영자 승인 전용 액션이다.
- **ExpireActionProposal** (제안 만료, 선언형) — 오래된 제안을 만료 처리한다. 만료된 제안은 승인할 수 없다.
- **RejectActionProposal** (제안 거절, 선언형) — 운영자가 제안을 거절한다. 거절 사유는 이후 에이전트 개선 데이터로 남는다.
- **CloseStore** (매장 휴업, 선언형) — 운영 중인 매장을 휴업 상태로 전환한다.
- **RecordBatch** (생산배치 등록, 함수 기반) — 제품과 수량을 받아 생산배치를 만들고 제품·매장에 연결한다.

## 함수

- **applyApprovedProposal** (write) — 승인된 ActionProposal의 대상 액션을 동일 적용기로 실행하고 상태를 전이한다.
- **expiringBatches** (read) — 지정한 일수 안에 소비기한이 도래하는 배치를 반환한다.
- **recordBatch** (write) — 배치번호를 채번하고 소비기한을 유통기한으로부터 계산한다.

## 에이전트

