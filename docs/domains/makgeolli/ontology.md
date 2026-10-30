# 온톨로지 스키마

생성일: 2026-10-30

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
| decidedParams (확정파라미터) | json |  |  |
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

### Batch — 양조배치

한 번의 양조. 발효→숙성→병입을 거치며 병입일과 제품 유통기한으로 소비기한이 정해진다.

- 기본키: `batchNo`
- 상태머신: fermenting→aging, aging→ready, ready→shipped, ready→wasted, fermenting→wasted, aging→wasted

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| batchNo (배치번호) | string | O |  |
| productRid (제품) | objectRef | O | O |
| tankRid (탱크) | objectRef |  | O |
| brewDate (양조일) | date | O | O |
| fermentationDueOn (발효완료예정일) | date | O | O |
| agingDueOn (숙성완료예정일) | date | O |  |
| fermentationTempC (발효목표온도(°C)) | decimal | O |  |
| agingTempC (숙성목표온도(°C)) | decimal | O |  |
| fermentedOn (발효완료일) | date |  |  |
| bottledOn (병입일) | date |  |  |
| expiresOn (소비기한) | date |  | O |
| volumeL (양조량(L)) | decimal | O |  |
| bottledQty (병입수량(병)) | integer |  |  |
| status (상태) | enum | O | O |

링크: `shipments` → Shipment, `readings` → TempReading, `stocks` → WarehouseStock, `wasteRecords` → WasteRecord, `product` → Product, `materials` → RawMaterial, `tank` → Tank

### Customer — 판매처

막걸리를 납품하는 유흥주점·편의점·마트·온라인 판매처.

- 기본키: `customerNo`
- 상태머신: active→suspended, suspended→active

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| customerNo (판매처번호) | string | O |  |
| name (명칭) | string | O | O |
| type (유형) | enum | O | O |
| region (지역) | string |  |  |
| status (상태) | enum | O | O |
| openedOn (거래시작일) | date |  |  |

링크: `orders` → SalesOrder, `outletStocks` → OutletStock, `shipments` → Shipment

### OutletStock — 판매처재고

판매처별·제품별 재고 수량. 판매처당 제품마다 한 건만 존재한다.

- 기본키: `stockNo`

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| stockNo (재고번호) | string | O |  |
| customerRid (판매처) | objectRef | O | O |
| productRid (제품) | objectRef | O | O |
| quantity (재고수량(병)) | integer | O |  |
| updatedOn (갱신일) | date | O |  |

링크: `customer` → Customer, `product` → Product

### Product — 제품

막걸리 양조장 SKU. 유통기한(≤30일)과 발효·숙성일수, 권장 온도 범위를 제품 속성으로 둔다.

- 기본키: `sku`

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| sku (SKU) | string | O |  |
| name (제품명) | string | O | O |
| category (분류) | enum | O | O |
| alcoholPercent (도수(%)) | decimal | O |  |
| shelfLifeDays (유통기한(일)) | integer | O |  |
| fermentationDays (발효일수) | integer | O |  |
| agingDays (숙성일수) | integer | O |  |
| fermentationTempMinC (발효권장최저온도(°C)) | decimal | O |  |
| fermentationTempMaxC (발효권장최고온도(°C)) | decimal | O |  |
| agingTempMinC (숙성권장최저온도(°C)) | decimal | O |  |
| agingTempMaxC (숙성권장최고온도(°C)) | decimal | O |  |
| volumeMl (용량(ml)) | integer | O |  |
| unitPrice (단가(원)) | integer | O |  |
| active (판매중) | boolean | O | O |

링크: `orderLines` → SalesOrderLine, `batches` → Batch, `outletStocks` → OutletStock, `warehouseStocks` → WarehouseStock

### RawMaterial — 원자재

양조 원자재. 현재재고와 발주시점을 추적해 재양조 전 필요량을 확보한다.

- 기본키: `materialNo`

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| materialNo (자재번호) | string | O |  |
| name (자재명) | string | O | O |
| unit (단위) | enum | O |  |
| unitCost (단위원가(원)) | integer | O |  |
| currentStock (현재재고) | decimal | O |  |
| reorderPoint (발주시점) | decimal | O |  |
| supplier (공급처) | string |  |  |

링크: `batches` → Batch

### SalesOrder — 판매주문

판매처 주문. 합계는 라인에서 계산해 저장한다.

- 기본키: `orderNo`
- 상태머신: draft→confirmed, confirmed→shipped, shipped→delivered, draft→cancelled, confirmed→cancelled

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| orderNo (주문번호) | string | O |  |
| customerRid (판매처) | objectRef | O | O |
| orderDate (주문일) | date | O | O |
| status (상태) | enum | O | O |
| totalAmount (총액(원)) | bigint |  | O |
| note (비고) | text |  |  |

링크: `customer` → Customer, `lines` → SalesOrderLine, `shipments` → Shipment

### SalesOrderLine — 주문라인

주문 한 행. 단가×수량으로 라인 금액을 검증한다.

- 기본키: `lineNo`

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| lineNo (라인번호) | string | O |  |
| orderRid (주문) | objectRef | O | O |
| productRid (제품) | objectRef | O | O |
| cases (수량(병)) | integer | O |  |
| unitPrice (단가(원)) | integer | O |  |
| lineAmount (라인금액(원)) | bigint | O |  |
| productName (제품명) | string |  |  |

링크: `product` → Product, `order` → SalesOrder

### Shipment — 출하

병입 완료 배치를 판매처로 출하한 기록.

- 기본키: `shipmentNo`
- 상태머신: in_transit→delivered, in_transit→cancelled

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| shipmentNo (출하번호) | string | O |  |
| shipDate (출하일) | date | O | O |
| batchRid (배치) | objectRef | O | O |
| customerRid (판매처) | objectRef | O | O |
| orderRid (주문) | objectRef |  | O |
| quantity (출하수량(병)) | integer | O |  |
| status (상태) | enum | O | O |
| deliveredOn (도착일) | date |  |  |

링크: `batch` → Batch, `customer` → Customer, `order` → SalesOrder

### Tank — 발효조

발효·숙성에 쓰는 탱크. 온도조절 가능 범위를 속성으로 두어 배치 목표온도 검증에 쓴다.

- 기본키: `tankNo`
- 상태머신: idle→in_use, in_use→idle, in_use→cleaning, cleaning→idle, idle→maintenance, maintenance→idle

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| tankNo (탱크번호) | string | O |  |
| name (명칭) | string | O |  |
| capacityL (용량(L)) | decimal | O |  |
| kind (구분) | enum | O |  |
| tempControl (온도조절) | boolean | O |  |
| tempMinC (조절최저온도(°C)) | decimal | O |  |
| tempMaxC (조절최고온도(°C)) | decimal | O |  |
| status (상태) | enum | O | O |

링크: `batches` → Batch

### TempReading — 온도측정

배치의 발효·숙성 온도 측정 기록. 배치 목표온도 범위 대비 허용여부를 판정한다.

- 기본키: `readingNo`

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| readingNo (측정번호) | string | O |  |
| batchRid (배치) | objectRef | O | O |
| recordedAt (측정시각) | text | O |  |
| tempC (측정온도(°C)) | decimal | O |  |
| stage (단계) | enum | O | O |
| inRange (범위내) | boolean | O | O |

링크: `batch` → Batch

### WarehouseStock — 창고재고

배치별 병입 재고. 배치당 한 건이며 FEFO(선입선출·소비기한순) 출하 판단에 쓴다.

- 기본키: `stockNo`

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| stockNo (재고번호) | string | O |  |
| batchRid (배치) | objectRef | O | O |
| productRid (제품) | objectRef | O | O |
| quantity (재고수량(병)) | integer | O |  |
| updatedOn (갱신일) | date | O |  |

링크: `batch` → Batch, `product` → Product

### WasteRecord — 폐기기록

배치 폐기 기록. 품질·유통기한·파손 사유를 구분해 집계한다.

- 기본키: `wasteNo`

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| wasteNo (폐기번호) | string | O |  |
| wastedOn (폐기일) | date | O | O |
| batchRid (배치) | objectRef | O | O |
| quantity (폐기수량(병)) | integer | O |  |
| reason (사유) | enum | O | O |

링크: `batch` → Batch

## 액션 타입

- **ApproveActionProposal** (제안 승인, 함수 기반) — 운영자가 제안을 승인하면 대상 액션이 동일한 검증·감사 경로로 실행된다. 운영자 승인 전용 액션이다.
- **ExpireActionProposal** (제안 만료, 선언형) — 오래된 제안을 만료 처리한다. 만료된 제안은 승인할 수 없다.
- **RejectActionProposal** (제안 거절, 선언형) — 운영자가 제안을 거절한다. 거절 사유는 이후 에이전트 개선 데이터로 남는다.
- **AdjustBatchTemp** (목표온도 조정, 함수 기반) — 온도 이탈 배치의 목표온도를 탱크 조절범위 내에서 변경한다.
- **AdjustWarehouseStock** (창고 재고 조정, 함수 기반) — 재고 실사 차이 등으로 창고 재고를 수동 조정한다. 에이전트가 제안할 수 없다.
- **CancelSalesOrder** (판매주문 취소, 선언형) — 작성 중이거나 확정된 판매주문을 취소한다.
- **CompleteAging** (숙성 완료·병입, 함수 기반) — 숙성 중 배치를 병입해 소비기한을 부여하고 창고 재고를 생성한다.
- **CompleteFermentation** (발효 완료, 함수 기반) — 발효 중 배치를 숙성 단계로 전환한다.
- **ConfirmSalesOrder** (판매주문 확정, 선언형) — 작성 중인 판매주문을 확정한다.
- **CreateBatch** (양조 시작, 함수 기반) — 제품·양조일·양조량으로 배치를 생성하고 파생일과 목표온도를 계산한다.
- **CreateSalesOrder** (판매주문 생성, 함수 기반) — 판매처 주문을 라인과 함께 생성하고 합계를 계산한다.
- **ReceiveShipment** (출하 입고, 함수 기반) — 배송 중 출하를 입고 처리하고 판매처 재고를 올린다.
- **RecordTempReading** (온도 측정 기록, 함수 기반) — 배치의 발효·숙성 온도를 기록하고 목표범위 대비 허용여부를 판정한다.
- **RestockMaterial** (원자재 입고, 함수 기반) — 원자재 입고분을 현재재고에 더한다. 에이전트가 제안할 수 없다.
- **ShipBatch** (배치 출하, 함수 기반) — 병입 완료 배치를 판매처로 출하하고 창고 재고를 차감한다.
- **UpsertCustomer** (판매처 등록/수정, 함수 기반) — 판매처번호로 판매처를 신규 등록하거나 기존 정보를 갱신한다.
- **UpsertProduct** (제품 등록/수정, 함수 기반) — SKU로 제품을 신규 등록하거나 기존 제품 정보를 갱신한다.
- **WasteBatch** (배치 폐기, 함수 기반) — 배치를 전부 또는 일부 폐기하고 폐기기록을 남긴다.

## 함수

- **applyApprovedProposal** (write) — 승인된 ActionProposal의 대상 액션을 동일 적용기로 실행하고 상태를 전이한다.
- **adjustBatchTemp** (write) — 온도 이탈 배치의 목표온도를 탱크 조절범위 내에서 변경한다.
- **adjustWarehouseStock** (write) — 재고 실사 차이 등으로 창고 재고를 수동 조정한다.
- **completeAging** (write) — 숙성 중 배치를 병입해 소비기한을 부여하고 창고 재고를 생성한다.
- **completeFermentation** (write) — 발효 중 배치를 숙성 단계로 전환한다.
- **createBatch** (write) — 배치를 생성하고 파생일·목표온도를 계산하며 탱크를 점유한다.
- **createSalesOrder** (write) — 판매처 주문을 라인과 함께 생성하고 합계를 계산한다.
- **expiringBatches** (read) — 지정한 일수 안에 소비기한이 도래하는 병입 완료 배치를 소비기한순으로 반환한다.
- **outletStock** (read) — 판매처별 제품 재고를 반환한다.
- **productionPipeline** (read) — 발효·숙성 중 배치의 진행률과 예정일, 목표온도를 반환한다.
- **receiveShipment** (write) — 배송 중 출하를 입고 처리하고 판매처 재고를 올린다.
- **recordTempReading** (write) — 배치의 발효·숙성 온도를 기록하고 목표범위 대비 허용여부를 판정한다.
- **reorderSuggestions** (read) — 최근 수요와 재고·제조 리드타임을 근거로 제품별 양조 제안량을 계산한다.
- **restockMaterial** (write) — 원자재 입고분을 현재재고에 더한다.
- **salesSummary** (read) — 기간별 매출·수량·상태별 주문수·상위 제품을 반환한다.
- **shipBatch** (write) — 병입 완료 배치를 판매처로 출하하고 창고 재고를 차감한다.
- **tempDeviations** (read) — 최근 측정에서 목표온도 범위를 벗어난 배치 목록을 반환한다.
- **upsertCustomer** (write) — 판매처번호로 판매처를 신규 등록하거나 기존 정보를 갱신한다.
- **upsertProduct** (write) — SKU로 제품을 신규 등록하거나 기존 제품 정보를 갱신한다.
- **warehouseStock** (read) — 배치별 병입 재고를 소비기한순(FEFO)으로 반환한다.
- **wasteBatch** (write) — 배치를 전부 또는 일부 폐기하고 폐기기록을 남긴다.
- **wasteHistory** (read) — 기간·제품별 폐기 기록을 사유별 집계와 함께 반환한다.

## 에이전트

- **brewPlannerAgent** (양조 계획 에이전트) — 제안 가능: CreateBatch, CompleteFermentation, CompleteAging, WasteBatch, AdjustBatchTemp
- **breweryOpsAgent** (양조장 운영 코파이럿) — 제안 가능: 없음
- **salesIntakeAgent** (판매 접수 에이전트) — 제안 가능: CreateSalesOrder, ConfirmSalesOrder, ShipBatch, ReceiveShipment
