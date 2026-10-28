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

/** 한 번의 생산 실행. 제품·수량·생산일·소비기한을 기록한다. */
export interface BatchProperties {
  /** 배치번호 */
  batchNo: string;
  /** 제품 */
  productRid: string;
  /** 생산일 */
  producedOn: string;
  /** 소비기한 */
  expiresOn: string;
  /** 생산수량 */
  quantity: number;
  /** 상태 */
  status: "planned" | "baked" | "shipped" | "wasted";
}

export interface Batch {
  rid: string;
  objectType: string;
  properties: BatchProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

/** 베이커리 SKU. 주류 도메인의 Product와 이름은 같지만 속성은 완전히 다르다. */
export interface ProductProperties {
  /** SKU */
  sku: string;
  /** 제품명 */
  name: string;
  /** 분류 */
  category: "식빵" | "단과자" | "케이크" | "페이스트리" | "기타";
  /** 유통기한(일) */
  shelfLifeDays: number;
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

/** 특정 제품을 특정 일자에 만들기로 한 생산 계획. 완료 시 배치가 생겨난다. */
export interface ProductionPlanProperties {
  /** 계획번호 */
  planNo: string;
  /** 계획일 */
  planDate: string;
  /** 제품 */
  productRid: string;
  /** 계획수량 */
  plannedQty: number;
  /** 생산수량 */
  producedQty?: number;
  /** 상태 */
  status: "planned" | "in_progress" | "completed" | "cancelled";
  /** 비고 */
  note?: string;
}

export interface ProductionPlan {
  rid: string;
  objectType: string;
  properties: ProductionPlanProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

/** 구운 배치를 매장으로 보내는 출하 단위. 출하 시점에 매장 재고가 반영된다. */
export interface ShipmentProperties {
  /** 출하번호 */
  shipmentNo: string;
  /** 출하일 */
  shipDate: string;
  /** 배치 */
  batchRid: string;
  /** 매장 */
  storeRid: string;
  /** 출하수량 */
  quantity: number;
  /** 상태 */
  status: "prepared" | "in_transit" | "delivered" | "cancelled";
  /** 입고일 */
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

/** 베이커리 제품을 판매하는 매장. */
export interface StoreProperties {
  /** 매장번호 */
  storeNo: string;
  /** 매장명 */
  name: string;
  /** 상태 */
  status: "active" | "closed";
  /** 개점일 */
  openedOn?: string;
}

export interface Store {
  rid: string;
  objectType: string;
  properties: StoreProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

/** 매장별·제품별 재고 수량. 매장당 제품마다 한 건만 존재한다. */
export interface StoreStockProperties {
  /** 재고번호 */
  stockNo: string;
  /** 매장 */
  storeRid: string;
  /** 제품 */
  productRid: string;
  /** 재고수량 */
  quantity: number;
  /** 갱신일 */
  updatedOn: string;
}

export interface StoreStock {
  rid: string;
  objectType: string;
  properties: StoreStockProperties;
  version?: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

/** 폐기된 배치와 사유. 배치 상태를 wasted로 바꾸는 유일한 근거가 된다. */
export interface WasteRecordProperties {
  /** 폐기번호 */
  wasteNo: string;
  /** 폐기일 */
  wastedOn: string;
  /** 배치 */
  batchRid: string;
  /** 폐기수량 */
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
  "Product",
  "ProductionPlan",
  "Shipment",
  "Store",
  "StoreStock",
  "WasteRecord",
] as const;
export type ObjectTypeName = (typeof OBJECT_TYPE_NAMES)[number];

export type ObjectPropertiesByName = {
  ActionProposal: ActionProposalProperties;
  AgentRun: AgentRunProperties;
  Batch: BatchProperties;
  Product: ProductProperties;
  ProductionPlan: ProductionPlanProperties;
  Shipment: ShipmentProperties;
  Store: StoreProperties;
  StoreStock: StoreStockProperties;
  WasteRecord: WasteRecordProperties;
};

export type ObjectByName = {
  ActionProposal: ActionProposal;
  AgentRun: AgentRun;
  Batch: Batch;
  Product: Product;
  ProductionPlan: ProductionPlan;
  Shipment: Shipment;
  Store: Store;
  StoreStock: StoreStock;
  WasteRecord: WasteRecord;
};
