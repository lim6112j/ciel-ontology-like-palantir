// GENERATED FILE — do not edit by hand.
// Regenerate with: uv run ontology export-client --out apps/web/src/generated
/** 에이전트가 제안한 액션. 운영자 승인 전에는 어떤 객체도 변경되지 않는다. */
export interface ActionProposalProperties {
  /** 제안번호 */
  proposalNo: string;
  /** 액션 */
  actionType: string;
  /** 파라미터 */
  params: unknown;
  /** 제안근거 */
  rationale: string;
  /** 신뢰도 */
  confidence?: number;
  /** 상태 */
  status: "proposed" | "approved" | "rejected" | "expired" | "failed";
  /** 사전검증결과 */
  violations?: unknown;
  /** 대상타입 */
  targetObjectType?: string;
  /** 대상객체 */
  targetRid?: string;
  /** 에이전트실행 */
  agentRunRid?: string;
  /** 승인자 */
  approvedBy?: string;
  /** 승인시각 */
  approvedAt?: string;
  /** 결정시각 */
  decidedAt?: string;
  /** 실행기록ID */
  resultingRunId?: string;
  /** 피드백 */
  feedbackNote?: string;
}

export interface ActionProposal {
  rid: string;
  objectType: string;
  properties: ActionProposalProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

/** 에이전트 호출 1건의 감사 기록. 도구 호출과 토큰 사용량을 보관한다. */
export interface AgentRunProperties {
  /** 실행번호 */
  runNo: string;
  /** 에이전트 */
  agentApiName: string;
  /** 모델 */
  model: string;
  /** 입력 */
  inputText: string;
  /** 도구호출수 */
  toolCallCount: number;
  /** 입력토큰 */
  inputTokens?: number;
  /** 출력토큰 */
  outputTokens?: number;
  /** 소요(ms) */
  latencyMs?: number;
  /** 상태 */
  status: "running" | "succeeded" | "failed" | "limited";
  /** 오류 */
  error?: string;
  /** 대화기록 */
  transcript?: unknown;
}

export interface AgentRun {
  rid: string;
  objectType: string;
  properties: AgentRunProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

/** 특정 일자에 한 기사·차량이 수행하는 배송 실행 단위. */
export interface DeliveryProperties {
  /** 배송번호 */
  deliveryNo: string;
  /** 배송일 */
  deliveryDate: string;
  /** 창고 */
  depotRid: string;
  /** 기사 */
  driverRid?: string;
  /** 차량 */
  vehicleRid?: string;
  /** 배송노선 */
  routeRid?: string;
  /** 상태 */
  status: "planned" | "dispatched" | "in_progress" | "completed" | "partially_completed" | "cancelled";
  /** 계획거리(km) */
  plannedDistanceKm?: number;
  /** 계획소요(분) */
  plannedDurationMin?: number;
  /** 정류장수 */
  totalStops?: number;
  /** 총케이스 */
  totalCases?: number;
  /** 출발시각 */
  startedAt?: string;
  /** 완료시각 */
  completedAt?: string;
}

export interface Delivery {
  rid: string;
  objectType: string;
  properties: DeliveryProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

/** 요일별 상시 배송 노선 정의. 특정 일자의 실행은 Delivery가 담당한다. */
export interface DeliveryRouteProperties {
  /** 노선코드 */
  routeCode: string;
  /** 노선명 */
  name: string;
  /** 요일 */
  weekday: number;
  /** 창고 */
  depotRid: string;
  /** 담당영업사원 */
  salesRepRid?: string;
  /** 운영중 */
  active: boolean;
}

export interface DeliveryRoute {
  rid: string;
  objectType: string;
  properties: DeliveryRouteProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

/** 배송의 개별 정류장. 한 정류장이 여러 발주를 처리할 수 있다. */
export interface DeliveryStopProperties {
  /** 정류장번호 */
  stopNo: string;
  /** 순번 */
  sequence: number;
  /** 상태 */
  status: "planned" | "arrived" | "completed" | "failed";
  /** 계획도착 */
  plannedAt?: string;
  /** 실제도착 */
  arrivedAt?: string;
  /** 완료시각 */
  completedAt?: string;
  /** 계획케이스 */
  plannedCases?: number;
  /** 실제케이스 */
  actualCases?: number;
  /** 실패사유 */
  failureReason?: "영업중아님" | "재고없음" | "거래처요청" | "차량문제" | "주소오류" | "기타";
  /** 실패상세 */
  failureNote?: string;
  /** 거래처 */
  outletRid: string;
  /** 배송 */
  deliveryRid: string;
}

export interface DeliveryStop {
  rid: string;
  objectType: string;
  properties: DeliveryStopProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface DepotProperties {
  /** 창고코드 */
  depotNo: string;
  /** 창고명 */
  name: string;
  /** 권역 */
  region: "수도권" | "충청" | "호남" | "영남" | "강원";
  /** 주소 */
  address?: string;
  /** 위도 */
  lat: number;
  /** 경도 */
  lon: number;
  /** 보관케이스 */
  capacityCases?: number;
}

export interface Depot {
  rid: string;
  objectType: string;
  properties: DepotProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface DriverProperties {
  /** 사번 */
  employeeNo: string;
  /** 이름 */
  name: string;
  /** 연락처 */
  phone?: string;
  /** 고용형태 */
  employmentType: "직영" | "지입";
  /** 운전면허 */
  licenseType: "1종보통" | "1종대형" | "2종보통";
  /** 상태 */
  status: "available" | "on_leave" | "inactive";
  /** 소속창고 */
  depotRid: string;
}

export interface Driver {
  rid: string;
  objectType: string;
  properties: DriverProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface DriverShiftProperties {
  /** 근무번호 */
  shiftNo: string;
  /** 근무일 */
  shiftDate: string;
  /** 출근시각 */
  startedAt?: string;
  /** 퇴근시각 */
  endedAt?: string;
  /** 상태 */
  status: "scheduled" | "working" | "finished" | "absent";
  /** 기사 */
  driverRid: string;
}

export interface DriverShift {
  rid: string;
  objectType: string;
  properties: DriverShiftProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface InvoiceLineProperties {
  /** 계산서라인번호 */
  invoiceLineNo: string;
  /** 납품케이스 */
  deliveredCases: number;
  /** 케이스단가(원) */
  unitPrice: number;
  /** 라인금액(원) */
  lineAmount: number;
  /** 제품 */
  productRid: string;
  /** 원발주라인 */
  orderLineRid?: string;
}

export interface InvoiceLine {
  rid: string;
  objectType: string;
  properties: InvoiceLineProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

/** 주류를 납품하는 소매점·음식점·유흥주점 등 거래처. 면허 정보는 보관하지만 v1에서 규제를 강제하지 않는다. */
export interface OutletProperties {
  /** 거래처코드 */
  outletNo: string;
  /** 거래처명 */
  name: string;
  /** 업태 */
  outletType: "소매점" | "일반음식점" | "유흥주점" | "편의점" | "마트" | "실수요자";
  /** 사업자등록번호 */
  bizRegNo?: string;
  /** 주류판매업면허번호 */
  licenseNo?: string;
  /** 면허종류 */
  licenseType?: "주류소매업" | "주정소매업" | "일반음식점" | "단란주점" | "유흥주점" | "없음";
  /** 주소 */
  address?: string;
  /** 위도 */
  lat?: number;
  /** 경도 */
  lon?: number;
  /** 배송요일 */
  deliveryWeekday?: number;
  /** 배송시간대 */
  deliveryWindow?: "오전" | "오후" | "종일";
  /** 상태 */
  status: "active" | "suspended" | "closed";
  /** 담당영업사원 */
  salesRepRid?: string;
  /** 담당창고 */
  depotRid?: string;
  /** 배송노선 */
  routeRid?: string;
  /** 비고 */
  note?: string;
}

export interface Outlet {
  rid: string;
  objectType: string;
  properties: OutletProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

/** 주류 SKU. 수량은 케이스 단위 정수로 관리한다. */
export interface ProductProperties {
  /** SKU */
  sku: string;
  /** 제품명 */
  name: string;
  /** 주종 */
  category: "소주" | "맥주" | "탁주" | "청주" | "양주" | "와인" | "기타";
  /** 제조사 */
  manufacturer?: string;
  /** 용량(ml) */
  volumeMl: number;
  /** 케이스당 병수 */
  unitsPerCase: number;
  /** 병당 단가(원) */
  unitPrice: number;
  /** 케이스 단가(원) */
  casePrice: number;
  /** 과세구분 */
  taxType?: "과세" | "면세";
  /** 알코올도수 */
  alcoholPercent?: number;
  /** 판매중 */
  active: boolean;
}

export interface Product {
  rid: string;
  objectType: string;
  properties: ProductProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

/** 납품 완료 시 생성되는 판매계산서. 단가·수량은 발행 시점 스냅샷이다. */
export interface SalesInvoiceProperties {
  /** 계산서번호 */
  invoiceNo: string;
  /** 발행일 */
  issueDate: string;
  /** 총액(원) */
  totalAmount: number;
  /** 세액(원) */
  taxAmount: number;
  /** 총케이스 */
  totalCases: number;
  /** 상태 */
  status: "issued" | "cancelled";
  /** 거래처 */
  outletRid: string;
}

export interface SalesInvoice {
  rid: string;
  objectType: string;
  properties: SalesInvoiceProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

/** 거래처 발주. 합계는 라인에서 계산해 저장한다. */
export interface SalesOrderProperties {
  /** 발주번호 */
  orderNo: string;
  /** 거래처 */
  outletRid: string;
  /** 영업사원 */
  salesRepRid?: string;
  /** 발주일 */
  orderDate: string;
  /** 희망납기일 */
  requestedDeliveryDate?: string;
  /** 상태 */
  status: "draft" | "submitted" | "confirmed" | "partially_fulfilled" | "fulfilled" | "cancelled";
  /** 접수경로 */
  channel: "phone" | "message" | "app" | "agent";
  /** 총액(원) */
  totalAmount?: number;
  /** 세액(원) */
  taxAmount?: number;
  /** 총케이스 */
  totalCases?: number;
  /** 비고 */
  note?: string;
  /** 생성한제안 */
  sourceProposalRid?: string;
}

export interface SalesOrder {
  rid: string;
  objectType: string;
  properties: SalesOrderProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface SalesOrderLineProperties {
  /** 라인번호 */
  lineNo: string;
  /** 주문케이스 */
  orderedCases: number;
  /** 케이스단가(원) */
  unitPrice: number;
  /** 라인금액(원) */
  lineAmount: number;
  /** 제품명 */
  productName: string;
  /** 제품 */
  productRid: string;
}

export interface SalesOrderLine {
  rid: string;
  objectType: string;
  properties: SalesOrderLineProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface SalesRepProperties {
  /** 사번 */
  employeeNo: string;
  /** 이름 */
  name: string;
  /** 연락처 */
  phone?: string;
  /** 담당구역 */
  territory?: string;
  /** 상태 */
  status: "active" | "inactive";
  /** 소속창고 */
  depotRid: string;
}

export interface SalesRep {
  rid: string;
  objectType: string;
  properties: SalesRepProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface VehicleProperties {
  /** 차량번호 */
  plateNo: string;
  /** 차종 */
  vehicleType: "1톤탑차" | "1.4톤탑차" | "2.5톤탑차" | "5톤윙바디";
  /** 적재케이스 */
  capacityCases: number;
  /** 적재중량(kg) */
  capacityWeightKg: number;
  /** 상태 */
  status: "available" | "maintenance" | "retired";
  /** 소속창고 */
  depotRid: string;
}

export interface Vehicle {
  rid: string;
  objectType: string;
  properties: VehicleProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export const OBJECT_TYPE_NAMES = [
  "ActionProposal",
  "AgentRun",
  "Delivery",
  "DeliveryRoute",
  "DeliveryStop",
  "Depot",
  "Driver",
  "DriverShift",
  "InvoiceLine",
  "Outlet",
  "Product",
  "SalesInvoice",
  "SalesOrder",
  "SalesOrderLine",
  "SalesRep",
  "Vehicle",
] as const;
export type ObjectTypeName = (typeof OBJECT_TYPE_NAMES)[number];

export type ObjectPropertiesByName = {
  ActionProposal: ActionProposalProperties;
  AgentRun: AgentRunProperties;
  Delivery: DeliveryProperties;
  DeliveryRoute: DeliveryRouteProperties;
  DeliveryStop: DeliveryStopProperties;
  Depot: DepotProperties;
  Driver: DriverProperties;
  DriverShift: DriverShiftProperties;
  InvoiceLine: InvoiceLineProperties;
  Outlet: OutletProperties;
  Product: ProductProperties;
  SalesInvoice: SalesInvoiceProperties;
  SalesOrder: SalesOrderProperties;
  SalesOrderLine: SalesOrderLineProperties;
  SalesRep: SalesRepProperties;
  Vehicle: VehicleProperties;
};

export type ObjectByName = {
  ActionProposal: ActionProposal;
  AgentRun: AgentRun;
  Delivery: Delivery;
  DeliveryRoute: DeliveryRoute;
  DeliveryStop: DeliveryStop;
  Depot: Depot;
  Driver: Driver;
  DriverShift: DriverShift;
  InvoiceLine: InvoiceLine;
  Outlet: Outlet;
  Product: Product;
  SalesInvoice: SalesInvoice;
  SalesOrder: SalesOrder;
  SalesOrderLine: SalesOrderLine;
  SalesRep: SalesRep;
  Vehicle: Vehicle;
};
