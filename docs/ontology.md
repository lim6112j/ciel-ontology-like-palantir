# 온톨로지 스키마

생성일: 2026-10-25

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

### Delivery — 배송

특정 일자에 한 기사·차량이 수행하는 배송 실행 단위.

- 기본키: `deliveryNo`
- 상태머신: planned→dispatched, planned→cancelled, dispatched→in_progress, dispatched→cancelled, in_progress→completed, in_progress→partially_completed, in_progress→cancelled

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| deliveryNo (배송번호) | string | O |  |
| deliveryDate (배송일) | date | O | O |
| depotRid (창고) | objectRef | O | O |
| driverRid (기사) | objectRef |  | O |
| vehicleRid (차량) | objectRef |  | O |
| routeRid (배송노선) | objectRef |  | O |
| status (상태) | enum | O | O |
| plannedDistanceKm (계획거리(km)) | decimal |  |  |
| plannedDurationMin (계획소요(분)) | integer |  |  |
| totalStops (정류장수) | integer |  |  |
| totalCases (총케이스) | integer |  |  |
| startedAt (출발시각) | timestamp |  |  |
| completedAt (완료시각) | timestamp |  |  |

링크: `stops` → DeliveryStop, `driver` → Driver, `vehicle` → Vehicle, `depot` → Depot, `route` → DeliveryRoute

### DeliveryRoute — 배송노선

요일별 상시 배송 노선 정의. 특정 일자의 실행은 Delivery가 담당한다.

- 기본키: `routeCode`

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| routeCode (노선코드) | string | O |  |
| name (노선명) | string | O |  |
| weekday (요일) | integer | O | O |
| depotRid (창고) | objectRef | O | O |
| salesRepRid (담당영업사원) | objectRef |  |  |
| active (운영중) | boolean | O | O |

링크: `outlets` → Outlet, `deliveries` → Delivery, `depot` → Depot, `salesRep` → SalesRep

### DeliveryStop — 납품처

배송의 개별 정류장. 한 정류장이 여러 발주를 처리할 수 있다.

- 기본키: `stopNo`
- 상태머신: planned→arrived, planned→failed, arrived→completed, arrived→failed

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| stopNo (정류장번호) | string | O |  |
| sequence (순번) | integer | O |  |
| status (상태) | enum | O | O |
| plannedAt (계획도착) | timestamp |  |  |
| arrivedAt (실제도착) | timestamp |  |  |
| completedAt (완료시각) | timestamp |  |  |
| plannedCases (계획케이스) | integer |  |  |
| actualCases (실제케이스) | integer |  |  |
| failureReason (실패사유) | enum |  |  |
| failureNote (실패상세) | text |  |  |
| outletRid (거래처) | objectRef | O | O |
| deliveryRid (배송) | objectRef | O | O |

링크: `outlet` → Outlet, `orders` → SalesOrder, `invoice` → SalesInvoice, `delivery` → Delivery

### Depot — 창고

- 기본키: `depotNo`

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| depotNo (창고코드) | string | O |  |
| name (창고명) | string | O | O |
| region (권역) | enum | O | O |
| address (주소) | string |  |  |
| lat (위도) | decimal | O |  |
| lon (경도) | decimal | O |  |
| capacityCases (보관케이스) | integer |  |  |

링크: `outlets` → Outlet, `deliveries` → Delivery, `drivers` → Driver, `vehicles` → Vehicle, `routes` → DeliveryRoute, `salesReps` → SalesRep

### Driver — 배송기사

- 기본키: `employeeNo`
- 상태머신: available→on_leave, on_leave→available, available→inactive, on_leave→inactive

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| employeeNo (사번) | string | O |  |
| name (이름) | string | O | O |
| phone (연락처) | string |  |  |
| employmentType (고용형태) | enum | O | O |
| licenseType (운전면허) | enum | O |  |
| status (상태) | enum | O | O |
| depotRid (소속창고) | objectRef | O | O |

링크: `deliveries` → Delivery, `depot` → Depot, `shifts` → DriverShift

### DriverShift — 기사근무

- 기본키: `shiftNo`
- 상태머신: scheduled→working, scheduled→absent, working→finished

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| shiftNo (근무번호) | string | O |  |
| shiftDate (근무일) | date | O | O |
| startedAt (출근시각) | timestamp |  |  |
| endedAt (퇴근시각) | timestamp |  |  |
| status (상태) | enum | O | O |
| driverRid (기사) | objectRef | O | O |

링크: `driver` → Driver

### InvoiceLine — 계산서라인

- 기본키: `invoiceLineNo`

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| invoiceLineNo (계산서라인번호) | string | O |  |
| deliveredCases (납품케이스) | integer | O |  |
| unitPrice (케이스단가(원)) | integer | O |  |
| lineAmount (라인금액(원)) | bigint | O |  |
| productRid (제품) | objectRef | O |  |
| orderLineRid (원발주라인) | objectRef |  |  |

링크: `invoice` → SalesInvoice, `product` → Product

### Outlet — 거래처

주류를 납품하는 소매점·음식점·유흥주점 등 거래처. 면허 정보는 보관하지만 v1에서 규제를 강제하지 않는다.

- 기본키: `outletNo`
- 상태머신: active→suspended, suspended→active, active→closed, suspended→closed, closed→active

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| outletNo (거래처코드) | string | O |  |
| name (거래처명) | string | O | O |
| outletType (업태) | enum | O | O |
| bizRegNo (사업자등록번호) | string |  |  |
| licenseNo (주류판매업면허번호) | string |  |  |
| licenseType (면허종류) | enum |  |  |
| address (주소) | string |  |  |
| lat (위도) | decimal |  |  |
| lon (경도) | decimal |  |  |
| deliveryWeekday (배송요일) | integer |  | O |
| deliveryWindow (배송시간대) | enum |  |  |
| status (상태) | enum | O | O |
| salesRepRid (담당영업사원) | objectRef |  | O |
| depotRid (담당창고) | objectRef |  | O |
| routeRid (배송노선) | objectRef |  | O |
| note (비고) | text |  |  |

링크: `salesRep` → SalesRep, `depot` → Depot, `orders` → SalesOrder, `route` → DeliveryRoute, `stops` → DeliveryStop

### Product — 제품

주류 SKU. 수량은 케이스 단위 정수로 관리한다.

- 기본키: `sku`

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| sku (SKU) | string | O |  |
| name (제품명) | string | O | O |
| category (주종) | enum | O | O |
| manufacturer (제조사) | string |  | O |
| volumeMl (용량(ml)) | integer | O |  |
| unitsPerCase (케이스당 병수) | integer | O |  |
| unitPrice (병당 단가(원)) | integer | O |  |
| casePrice (케이스 단가(원)) | integer | O |  |
| taxType (과세구분) | enum |  |  |
| alcoholPercent (알코올도수) | decimal |  |  |
| active (판매중) | boolean | O | O |

링크: `orderLines` → SalesOrderLine, `invoiceLines` → InvoiceLine

### SalesInvoice — 판매계산서

납품 완료 시 생성되는 판매계산서. 단가·수량은 발행 시점 스냅샷이다.

- 기본키: `invoiceNo`

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| invoiceNo (계산서번호) | string | O |  |
| issueDate (발행일) | date | O | O |
| totalAmount (총액(원)) | bigint | O | O |
| taxAmount (세액(원)) | bigint | O |  |
| totalCases (총케이스) | integer | O |  |
| status (상태) | enum | O | O |
| outletRid (거래처) | objectRef | O | O |

링크: `order` → SalesOrder, `lines` → InvoiceLine, `stop` → DeliveryStop

### SalesOrder — 발주

거래처 발주. 합계는 라인에서 계산해 저장한다.

- 기본키: `orderNo`
- 상태머신: draft→submitted, submitted→confirmed, submitted→cancelled, draft→cancelled, confirmed→partially_fulfilled, confirmed→fulfilled, confirmed→cancelled, partially_fulfilled→partially_fulfilled, partially_fulfilled→fulfilled

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| orderNo (발주번호) | string | O |  |
| outletRid (거래처) | objectRef | O | O |
| salesRepRid (영업사원) | objectRef |  | O |
| orderDate (발주일) | date | O | O |
| requestedDeliveryDate (희망납기일) | date |  | O |
| status (상태) | enum | O | O |
| channel (접수경로) | enum | O |  |
| totalAmount (총액(원)) | bigint |  | O |
| taxAmount (세액(원)) | bigint |  |  |
| totalCases (총케이스) | integer |  |  |
| note (비고) | text |  |  |
| sourceProposalRid (생성한제안) | objectRef |  |  |

링크: `outlet` → Outlet, `salesRep` → SalesRep, `lines` → SalesOrderLine, `invoices` → SalesInvoice, `stop` → DeliveryStop

### SalesOrderLine — 발주라인

- 기본키: `lineNo`

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| lineNo (라인번호) | string | O |  |
| orderedCases (주문케이스) | integer | O |  |
| unitPrice (케이스단가(원)) | integer | O |  |
| lineAmount (라인금액(원)) | bigint | O |  |
| productName (제품명) | string | O |  |
| productRid (제품) | objectRef | O | O |

링크: `order` → SalesOrder, `product` → Product

### SalesRep — 영업사원

- 기본키: `employeeNo`
- 상태머신: active→inactive, inactive→active

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| employeeNo (사번) | string | O |  |
| name (이름) | string | O | O |
| phone (연락처) | string |  |  |
| territory (담당구역) | string |  | O |
| status (상태) | enum | O |  |
| depotRid (소속창고) | objectRef | O | O |

링크: `outlets` → Outlet, `orders` → SalesOrder, `routes` → DeliveryRoute, `depot` → Depot

### Vehicle — 차량

- 기본키: `plateNo`
- 상태머신: available→maintenance, maintenance→available, available→retired, maintenance→retired

| 속성 | 타입 | 필수 | 인덱스 |
|---|---|---|---|
| plateNo (차량번호) | string | O |  |
| vehicleType (차종) | enum | O |  |
| capacityCases (적재케이스) | integer | O |  |
| capacityWeightKg (적재중량(kg)) | integer | O |  |
| status (상태) | enum | O | O |
| depotRid (소속창고) | objectRef | O | O |

링크: `deliveries` → Delivery, `depot` → Depot

## 액션 타입

- **AddOrderLine** (발주라인 추가, 함수 기반) — 초안 발주에 제품 라인을 추가하고 합계를 다시 계산한다.
- **ApproveActionProposal** (제안 승인, 함수 기반) — 운영자가 제안을 승인하면 대상 액션이 동일한 검증·감사 경로로 실행된다. 운영자 승인 전용 액션이다.
- **ArriveAtStop** (정류장 도착, 선언형) — 기사가 납품처에 도착했음을 기록한다.
- **CancelSalesOrder** (발주 취소, 선언형) — 확정 전 발주를 취소한다. 배송이 시작된 발주는 취소할 수 없다.
- **CompleteDelivery** (배송 완료, 함수 기반) — 모든 정류장을 마친 배송을 완료 처리한다. 실패 정류장이 있으면 부분 완료가 된다.
- **CompleteStop** (납품 완료, 함수 기반) — 납품을 완료하고 판매계산서를 발행하며 발주 상태를 갱신한다.
- **ConfirmSalesOrder** (발주 확정, 선언형) — 제출된 발주를 확정해 배차 대상으로 만든다.
- **CreateSalesOrder** (발주 생성, 함수 기반) — 거래처·영업사원·발주일과 라인을 받아 초안 발주와 라인을 함께 만든다.
- **DispatchDelivery** (배송 출발 준비, 선언형) — 계획된 배송을 출발 준비 상태로 전이한다.
- **ExpireActionProposal** (제안 만료, 선언형) — 오래된 제안을 만료 처리한다. 만료된 제안은 승인할 수 없다.
- **FailStop** (납품 실패, 선언형) — 납품 실패 사유를 기록한다. 실패한 정류장은 재배차 대상이 된다.
- **PlanDeliveries** (배송 계획, 함수 기반) — 지정 일자의 확정 발주로 배송·정류장을 생성한다. 요일·용량·거리 순회를 적용한다.
- **ReassignDriver** (기사 재배정, 함수 기반) — 배송의 담당 기사·차량을 교체한다.
- **ReassignStop** (정류장 재배차, 함수 기반) — 실패하거나 미완료된 정류장을 다른 배송으로 옮긴다.
- **RegisterDriver** (기사 등록, 선언형) — 신규 배송기사를 등록한다.
- **RegisterVehicle** (차량 등록, 선언형) — 신규 배송차량을 등록한다.
- **RejectActionProposal** (제안 거절, 선언형) — 운영자가 제안을 거절한다. 거절 사유는 이후 에이전트 개선 데이터로 남는다.
- **RemoveOrderLine** (발주라인 삭제, 함수 기반) — 초안 발주에서 라인을 제거하고 합계를 다시 계산한다.
- **SetDriverAvailability** (기사 가용상태 변경, 선언형) — 기사의 가용·휴무·비활성 상태를 변경한다.
- **SetOutletDeliveryDay** (배송요일 변경, 선언형) — 거래처의 정기 배송요일을 변경한다.
- **SetStopSequence** (정류장 순번 변경, 선언형) — 배송 계획을 출발 전에 수동으로 조정한다.
- **StartDelivery** (배송 시작, 함수 기반) — 기사가 배송을 시작한다. 배송 상태와 기사 근무를 함께 갱신한다.
- **SubmitSalesOrder** (발주 제출, 선언형) — 초안 발주를 제출 상태로 전이한다. 라인이 없으면 거부된다.
- **UpsertDeliveryRoute** (배송노선 등록/수정, 함수 기반) — 요일별 상시 배송노선을 만들거나 수정한다.
- **UpsertOutlet** (거래처 등록/수정, 함수 기반) — 거래처를 신규 등록하거나 기존 거래처 정보를 갱신한다.

## 함수

- **computeOrderTotals** (read) — 라인 금액과 케이스 수를 합산한다. 세액은 과세 제품 합계의 10%다.
- **validateOrderLine** (read) — 제품 판매 여부와 최소 주문 수량을 확인한다.
- **findAreaPriceRule** (read) — 창고 권역과 거래처 업태에 맞는 공급가를 반환한다.
- **checkVehicleCapacity** (read) — 후보 정류장 집합의 케이스·중량이 차량 한도를 넘지 않는지 확인한다.
- **detectDeliveryExceptions** (read) — 지연·실패 정류장, 용량 초과, 미배정 발주를 결정적으로 찾아낸다.
- **driverPerformance** (read) — 기간 내 완료 정류장, 정시율, 배송 케이스를 집계한다.
- **forecastOutletDemand** (read) — 최근 4주 이동평균으로 거래처·제품별 케이스 수요를 추정한다.
- **scoreOutletCredit** (read) — 최근 주문 패턴과 실패 정류장 비율로 위험 점수를 계산한다.
- **createSalesOrder** (write) — 초안 발주와 라인을 만들고 합계를 계산한다.
- **addOrderLine** (write) — 초안 발주에 라인을 추가하고 합계를 재계산한다.
- **removeOrderLine** (write) — 초안 발주에서 라인을 제거하고 합계를 재계산한다.
- **startDelivery** (write) — 배송을 진행중으로 바꾸고 기사 근무를 기록한다.
- **completeDelivery** (write) — 정류장 결과에 따라 완료 또는 부분 완료로 전이한다.
- **reassignDriver** (write) — 배송의 기사·차량을 교체한다.
- **reassignStop** (write) — 정류장을 다른 배송으로 옮기고 순번을 재정렬한다.
- **upsertOutlet** (write) — 거래처를 신규 등록하거나 갱신한다.
- **upsertDeliveryRoute** (write) — 요일별 상시 노선을 만들거나 갱신한다.
- **planDeliveries** (write) — 확정 발주를 요일·창고로 묶어 최근접 순회로 동선을 만들고 배송·정류장을 생성한다.
- **completeStop** (write) — 정류장을 완료하고 판매계산서·계산서 라인을 생성해 발주 상태를 갱신한다.
- **applyApprovedProposal** (write) — 승인된 ActionProposal의 대상 액션을 동일 적용기로 실행하고 상태를 전이한다.
- **recordDriverShift** (write) — 배송 시작 시 당일 근무를 working으로 생성한다.

## 에이전트

- **dispatchAgent** (배송 배차 에이전트) — 제안 가능: PlanDeliveries, ReassignDriver, ReassignStop
- **exceptionAgent** (배송 예외 처리 에이전트) — 제안 가능: ReassignStop, ReassignDriver, FailStop, CompleteStop
- **opsCopilotAgent** (운영 코파일럿) — 제안 가능: 없음
- **orderIntakeAgent** (발주 접수 에이전트) — 제안 가능: CreateSalesOrder, SubmitSalesOrder
