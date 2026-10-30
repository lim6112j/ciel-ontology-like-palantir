// GENERATED FILE — do not edit by hand.
// Regenerate with: uv run ontology export-web
/** 에이전트가 제안한 액션. 운영자 승인 전에는 어떤 객체도 변경되지 않는다. */
export interface ActionProposalProperties {
  /** 제안번호 */
  proposalNo: string;
  /** 액션 */
  actionType: string;
  /** 파라미터 */
  params: unknown;
  /** 확정파라미터 */
  decidedParams?: unknown;
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

/** 한 번의 양조. 발효→숙성→병입을 거치며 병입일과 제품 유통기한으로 소비기한이 정해진다. */
export interface BatchProperties {
  /** 배치번호 */
  batchNo: string;
  /** 제품 */
  productRid: string;
  /** 탱크 */
  tankRid?: string;
  /** 양조일 */
  brewDate: string;
  /** 발효완료예정일 */
  fermentationDueOn: string;
  /** 숙성완료예정일 */
  agingDueOn: string;
  /** 발효목표온도(°C) */
  fermentationTempC: number;
  /** 숙성목표온도(°C) */
  agingTempC: number;
  /** 발효완료일 */
  fermentedOn?: string;
  /** 병입일 */
  bottledOn?: string;
  /** 소비기한 */
  expiresOn?: string;
  /** 양조량(L) */
  volumeL: number;
  /** 병입수량(병) */
  bottledQty?: number;
  /** 상태 */
  status: "fermenting" | "aging" | "ready" | "shipped" | "wasted";
}

export interface Batch {
  rid: string;
  objectType: string;
  properties: BatchProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

/** 막걸리를 납품하는 유흥주점·편의점·마트·온라인 판매처. */
export interface CustomerProperties {
  /** 판매처번호 */
  customerNo: string;
  /** 명칭 */
  name: string;
  /** 유형 */
  type: "유흥주점" | "편의점" | "대형마트" | "온라인" | "직영점";
  /** 지역 */
  region?: string;
  /** 상태 */
  status: "active" | "suspended";
  /** 거래시작일 */
  openedOn?: string;
}

export interface Customer {
  rid: string;
  objectType: string;
  properties: CustomerProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

/** 판매처별·제품별 재고 수량. 판매처당 제품마다 한 건만 존재한다. */
export interface OutletStockProperties {
  /** 재고번호 */
  stockNo: string;
  /** 판매처 */
  customerRid: string;
  /** 제품 */
  productRid: string;
  /** 재고수량(병) */
  quantity: number;
  /** 갱신일 */
  updatedOn: string;
}

export interface OutletStock {
  rid: string;
  objectType: string;
  properties: OutletStockProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

/** 막걸리 양조장 SKU. 유통기한(≤30일)과 발효·숙성일수, 권장 온도 범위를 제품 속성으로 둔다. */
export interface ProductProperties {
  /** SKU */
  sku: string;
  /** 제품명 */
  name: string;
  /** 분류 */
  category: "생막걸리" | "탁주" | "청주" | "스파클링" | "과실주";
  /** 도수(%) */
  alcoholPercent: number;
  /** 유통기한(일) */
  shelfLifeDays: number;
  /** 발효일수 */
  fermentationDays: number;
  /** 숙성일수 */
  agingDays: number;
  /** 발효권장최저온도(°C) */
  fermentationTempMinC: number;
  /** 발효권장최고온도(°C) */
  fermentationTempMaxC: number;
  /** 숙성권장최저온도(°C) */
  agingTempMinC: number;
  /** 숙성권장최고온도(°C) */
  agingTempMaxC: number;
  /** 용량(ml) */
  volumeMl: number;
  /** 단가(원) */
  unitPrice: number;
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

/** 양조 원자재. 현재재고와 발주시점을 추적해 재양조 전 필요량을 확보한다. */
export interface RawMaterialProperties {
  /** 자재번호 */
  materialNo: string;
  /** 자재명 */
  name: string;
  /** 단위 */
  unit: "kg" | "L" | "g";
  /** 단위원가(원) */
  unitCost: number;
  /** 현재재고 */
  currentStock: number;
  /** 발주시점 */
  reorderPoint: number;
  /** 공급처 */
  supplier?: string;
}

export interface RawMaterial {
  rid: string;
  objectType: string;
  properties: RawMaterialProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

/** 판매처 주문. 합계는 라인에서 계산해 저장한다. */
export interface SalesOrderProperties {
  /** 주문번호 */
  orderNo: string;
  /** 판매처 */
  customerRid: string;
  /** 주문일 */
  orderDate: string;
  /** 상태 */
  status: "draft" | "confirmed" | "shipped" | "delivered" | "cancelled";
  /** 총액(원) */
  totalAmount?: number;
  /** 비고 */
  note?: string;
}

export interface SalesOrder {
  rid: string;
  objectType: string;
  properties: SalesOrderProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

/** 주문 한 행. 단가×수량으로 라인 금액을 검증한다. */
export interface SalesOrderLineProperties {
  /** 라인번호 */
  lineNo: string;
  /** 주문 */
  orderRid: string;
  /** 제품 */
  productRid: string;
  /** 수량(병) */
  cases: number;
  /** 단가(원) */
  unitPrice: number;
  /** 라인금액(원) */
  lineAmount: number;
  /** 제품명 */
  productName?: string;
}

export interface SalesOrderLine {
  rid: string;
  objectType: string;
  properties: SalesOrderLineProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

/** 병입 완료 배치를 판매처로 출하한 기록. */
export interface ShipmentProperties {
  /** 출하번호 */
  shipmentNo: string;
  /** 출하일 */
  shipDate: string;
  /** 배치 */
  batchRid: string;
  /** 판매처 */
  customerRid: string;
  /** 주문 */
  orderRid?: string;
  /** 출하수량(병) */
  quantity: number;
  /** 상태 */
  status: "in_transit" | "delivered" | "cancelled";
  /** 도착일 */
  deliveredOn?: string;
}

export interface Shipment {
  rid: string;
  objectType: string;
  properties: ShipmentProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

/** 발효·숙성에 쓰는 탱크. 온도조절 가능 범위를 속성으로 두어 배치 목표온도 검증에 쓴다. */
export interface TankProperties {
  /** 탱크번호 */
  tankNo: string;
  /** 명칭 */
  name: string;
  /** 용량(L) */
  capacityL: number;
  /** 구분 */
  kind: "발효조" | "숙성조";
  /** 온도조절 */
  tempControl: boolean;
  /** 조절최저온도(°C) */
  tempMinC: number;
  /** 조절최고온도(°C) */
  tempMaxC: number;
  /** 상태 */
  status: "idle" | "in_use" | "cleaning" | "maintenance";
}

export interface Tank {
  rid: string;
  objectType: string;
  properties: TankProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

/** 배치의 발효·숙성 온도 측정 기록. 배치 목표온도 범위 대비 허용여부를 판정한다. */
export interface TempReadingProperties {
  /** 측정번호 */
  readingNo: string;
  /** 배치 */
  batchRid: string;
  /** 측정시각 */
  recordedAt: string;
  /** 측정온도(°C) */
  tempC: number;
  /** 단계 */
  stage: "fermentation" | "aging";
  /** 범위내 */
  inRange: boolean;
}

export interface TempReading {
  rid: string;
  objectType: string;
  properties: TempReadingProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

/** 배치별 병입 재고. 배치당 한 건이며 FEFO(선입선출·소비기한순) 출하 판단에 쓴다. */
export interface WarehouseStockProperties {
  /** 재고번호 */
  stockNo: string;
  /** 배치 */
  batchRid: string;
  /** 제품 */
  productRid: string;
  /** 재고수량(병) */
  quantity: number;
  /** 갱신일 */
  updatedOn: string;
}

export interface WarehouseStock {
  rid: string;
  objectType: string;
  properties: WarehouseStockProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

/** 배치 폐기 기록. 품질·유통기한·파손 사유를 구분해 집계한다. */
export interface WasteRecordProperties {
  /** 폐기번호 */
  wasteNo: string;
  /** 폐기일 */
  wastedOn: string;
  /** 배치 */
  batchRid: string;
  /** 폐기수량(병) */
  quantity: number;
  /** 사유 */
  reason: "quality" | "expiry" | "damage" | "other";
}

export interface WasteRecord {
  rid: string;
  objectType: string;
  properties: WasteRecordProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export const OBJECT_TYPE_NAMES = [
  "ActionProposal",
  "AgentRun",
  "Batch",
  "Customer",
  "OutletStock",
  "Product",
  "RawMaterial",
  "SalesOrder",
  "SalesOrderLine",
  "Shipment",
  "Tank",
  "TempReading",
  "WarehouseStock",
  "WasteRecord",
] as const;
export type ObjectTypeName = (typeof OBJECT_TYPE_NAMES)[number];

export type ObjectPropertiesByName = {
  ActionProposal: ActionProposalProperties;
  AgentRun: AgentRunProperties;
  Batch: BatchProperties;
  Customer: CustomerProperties;
  OutletStock: OutletStockProperties;
  Product: ProductProperties;
  RawMaterial: RawMaterialProperties;
  SalesOrder: SalesOrderProperties;
  SalesOrderLine: SalesOrderLineProperties;
  Shipment: ShipmentProperties;
  Tank: TankProperties;
  TempReading: TempReadingProperties;
  WarehouseStock: WarehouseStockProperties;
  WasteRecord: WasteRecordProperties;
};

export type ObjectByName = {
  ActionProposal: ActionProposal;
  AgentRun: AgentRun;
  Batch: Batch;
  Customer: Customer;
  OutletStock: OutletStock;
  Product: Product;
  RawMaterial: RawMaterial;
  SalesOrder: SalesOrder;
  SalesOrderLine: SalesOrderLine;
  Shipment: Shipment;
  Tank: Tank;
  TempReading: TempReading;
  WarehouseStock: WarehouseStock;
  WasteRecord: WasteRecord;
};
