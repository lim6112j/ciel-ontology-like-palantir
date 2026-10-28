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

링크: `shipments` → Shipment, `wasteRecords` → WasteRecord, `plan` → ProductionPlan, `product` → Product, `store` → Store

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

링크: `plans` → ProductionPlan, `batches` → Batch, `stocks` → StoreStock

### ProductionPlan — 생산계획

특정 제품을 특정 일자에 만들기로 한 생산 계획. 완료 시 배치가 생겨난다.

- 기본키: `planNo`
- 상태머신: planned→in_progress, in_progress→completed, planned→cancelled, in_progress→cancelled

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| planNo (계획번호) | string | O |  |
| planDate (계획일) | date | O | O |
| productRid (제품) | objectRef | O | O |
| plannedQty (계획수량) | integer | O |  |
| producedQty (생산수량) | integer |  |  |
| status (상태) | enum | O | O |
| note (비고) | text |  |  |

링크: `batches` → Batch, `product` → Product

### Shipment — 배치출하

구운 배치를 매장으로 보내는 출하 단위. 출하 시점에 매장 재고가 반영된다.

- 기본키: `shipmentNo`
- 상태머신: prepared→in_transit, in_transit→delivered, prepared→cancelled, in_transit→cancelled

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| shipmentNo (출하번호) | string | O |  |
| shipDate (출하일) | date | O | O |
| batchRid (배치) | objectRef | O | O |
| storeRid (매장) | objectRef | O | O |
| quantity (출하수량) | integer | O |  |
| status (상태) | enum | O | O |
| deliveredOn (입고일) | date |  |  |

링크: `batch` → Batch, `store` → Store

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

링크: `batches` → Batch, `shipments` → Shipment, `stocks` → StoreStock

### StoreStock — 매장재고

매장별·제품별 재고 수량. 매장당 제품마다 한 건만 존재한다.

- 기본키: `stockNo`

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| stockNo (재고번호) | string | O |  |
| storeRid (매장) | objectRef | O | O |
| productRid (제품) | objectRef | O | O |
| quantity (재고수량) | integer | O |  |
| updatedOn (갱신일) | date | O |  |

링크: `product` → Product, `store` → Store

### WasteRecord — 폐기기록

폐기된 배치와 사유. 배치 상태를 wasted로 바꾸는 유일한 근거가 된다.

- 기본키: `wasteNo`

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| wasteNo (폐기번호) | string | O |  |
| wastedOn (폐기일) | date | O | O |
| batchRid (배치) | objectRef | O | O |
| quantity (폐기수량) | integer | O |  |
| reason (사유) | enum | O | O |

링크: `batch` → Batch

## 액션 타입

- **ApproveActionProposal** (제안 승인, 함수 기반) — 운영자가 제안을 승인하면 대상 액션이 동일한 검증·감사 경로로 실행된다. 운영자 승인 전용 액션이다.
- **ExpireActionProposal** (제안 만료, 선언형) — 오래된 제안을 만료 처리한다. 만료된 제안은 승인할 수 없다.
- **RejectActionProposal** (제안 거절, 선언형) — 운영자가 제안을 거절한다. 거절 사유는 이후 에이전트 개선 데이터로 남는다.
- **AdjustStoreStock** (매장 재고 조정, 함수 기반) — 재고 실사 차이 등으로 매장 재고를 수동 조정한다. 에이전트가 제안할 수 없다.
- **CloseStore** (매장 휴업, 선언형) — 운영 중인 매장을 휴업 상태로 전환한다.
- **CompleteProductionPlan** (생산 완료, 함수 기반) — 진행 중 생산계획을 완료 처리하고 실제 생산수량만큼 구운 배치를 만든다.
- **CreateProductionPlan** (생산계획 생성, 함수 기반) — 제품과 수량으로 생산계획을 만든다. 판매 중지 제품은 계획할 수 없다.
- **ReceiveShipment** (출하 입고, 함수 기반) — 배송 중인 출하를 매장 입고 처리한다. 재고는 출하 시점에 이미 반영되었다.
- **RecordBatch** (생산배치 등록, 함수 기반) — 제품과 수량을 받아 생산배치를 만들고 제품·매장에 연결한다.
- **ShipBatch** (배치 출하, 함수 기반) — 구운 배치를 매장으로 출하한다. 출하 수량만큼 매장 재고가 늘어난다.
- **StartProductionPlan** (생산 시작, 선언형) — 계획된 생산계획을 진행 중으로 전환한다.
- **UpsertProduct** (제품 등록/수정, 함수 기반) — SKU로 제품을 신규 등록하거나 기존 제품 정보를 갱신한다.
- **UpsertStore** (매장 등록/수정, 함수 기반) — 매장번호로 매장을 신규 등록하거나 기존 매장 정보를 갱신한다.
- **WasteBatch** (배치 폐기, 함수 기반) — 계획 또는 구운 상태의 배치를 폐기한다. 부분 폐기면 잔량이 배치에 남는다.

## 함수

- **applyApprovedProposal** (write) — 승인된 ActionProposal의 대상 액션을 동일 적용기로 실행하고 상태를 전이한다.
- **adjustStoreStock** (write) — 매장·제품 재고를 지정한 양만큼 조정한다. 음수 결과는 금지된다.
- **completeProductionPlan** (write) — 생산계획을 완료하고 실제 수량만큼 구운 배치를 생성·연결한다.
- **expiringBatches** (read) — 지정한 일수 안에 소비기한이 도래하는 배치를 반환한다.
- **planProduction** (write) — 제품 활성 여부를 확인하고 생산계획을 생성한다.
- **productionSummary** (read) — 지정 일자의 생산계획과 배치 현황을 요약해 반환한다.
- **receiveShipment** (write) — 배송 중 출하를 입고 처리한다. 재고는 출하 시점에 이미 반영되었다.
- **recordBatch** (write) — 배치번호를 채번하고 소비기한을 유통기한으로부터 계산한다.
- **shipBatch** (write) — 배치를 매장으로 출하하고 출하수량만큼 매장 재고를 올린다.
- **storeStock** (read) — 매장별 재고 현황을 제품명과 함께 반환한다.
- **upsertProduct** (write) — SKU로 제품을 찾아 있으면 수정, 없으면 생성한다.
- **upsertStore** (write) — 매장번호로 매장을 찾아 있으면 수정, 없으면 생성한다.
- **wasteBatch** (write) — 폐기기록을 남기고 배치 상태를 wasted로 바꾼다. 부분 폐기는 잔량만 남긴다.

## 에이전트

- **bakeryOpsAgent** (베이커리 운영 코파이럿) — 제안 가능: 없음
- **batchPlannerAgent** (생산 계획 에이전트) — 제안 가능: CreateProductionPlan, StartProductionPlan, CompleteProductionPlan, ShipBatch, WasteBatch
