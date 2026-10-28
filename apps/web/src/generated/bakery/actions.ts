// GENERATED FILE — do not edit by hand.
// Regenerate with: uv run ontology export-web
import type { ObjectReference } from "./client";/** 운영자가 제안을 승인하면 대상 액션이 동일한 검증·감사 경로로 실행된다. 운영자 승인 전용 액션이다. */
export interface ApproveActionProposalParams {
  /** 제안 */
  proposal: ObjectReference;
  /** 수정된파라미터 */
  approvedParams?: unknown;
  /** 승인메모 */
  note?: string;
}

/** 오래된 제안을 만료 처리한다. 만료된 제안은 승인할 수 없다. */
export interface ExpireActionProposalParams {
  /** 제안 */
  proposal: ObjectReference;
  /** 만료사유 */
  reason?: string;
}

/** 운영자가 제안을 거절한다. 거절 사유는 이후 에이전트 개선 데이터로 남는다. */
export interface RejectActionProposalParams {
  /** 제안 */
  proposal: ObjectReference;
  /** 거절사유 */
  reason: string;
}

/** 재고 실사 차이 등으로 매장 재고를 수동 조정한다. 에이전트가 제안할 수 없다. */
export interface AdjustStoreStockParams {
  /** 매장 */
  store: ObjectReference;
  /** 제품 */
  product: ObjectReference;
  /** 조정량 */
  delta: number;
}

/** 운영 중인 매장을 휴업 상태로 전환한다. */
export interface CloseStoreParams {
  /** 매장 */
  store: ObjectReference;
}

/** 진행 중 생산계획을 완료 처리하고 실제 생산수량만큼 구운 배치를 만든다. */
export interface CompleteProductionPlanParams {
  /** 생산계획 */
  plan: ObjectReference;
  /** 생산수량 */
  producedQty?: number;
}

/** 제품과 수량으로 생산계획을 만든다. 판매 중지 제품은 계획할 수 없다. */
export interface CreateProductionPlanParams {
  /** 제품 */
  product: ObjectReference;
  /** 계획일 */
  planDate: string;
  /** 계획수량 */
  plannedQty: number;
  /** 비고 */
  note?: string;
}

/** 배송 중인 출하를 매장 입고 처리한다. 재고는 출하 시점에 이미 반영되었다. */
export interface ReceiveShipmentParams {
  /** 출하 */
  shipment: ObjectReference;
  /** 입고일 */
  receivedOn?: string;
}

/** 제품과 수량을 받아 생산배치를 만들고 제품·매장에 연결한다. */
export interface RecordBatchParams {
  /** 제품 */
  product: ObjectReference;
  /** 매장 */
  store?: ObjectReference;
  /** 수량 */
  quantity: number;
  /** 생산일 */
  producedOn: string;
}

/** 구운 배치를 매장으로 출하한다. 출하 수량만큼 매장 재고가 늘어난다. */
export interface ShipBatchParams {
  /** 배치 */
  batch: ObjectReference;
  /** 매장 */
  store: ObjectReference;
  /** 출하수량 */
  quantity?: number;
  /** 출하일 */
  shipDate?: string;
}

/** 계획된 생산계획을 진행 중으로 전환한다. */
export interface StartProductionPlanParams {
  /** 생산계획 */
  plan: ObjectReference;
}

/** SKU로 제품을 신규 등록하거나 기존 제품 정보를 갱신한다. */
export interface UpsertProductParams {
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
  active?: boolean;
}

/** 매장번호로 매장을 신규 등록하거나 기존 매장 정보를 갱신한다. */
export interface UpsertStoreParams {
  /** 매장번호 */
  storeNo: string;
  /** 매장명 */
  name: string;
  /** 개점일 */
  openedOn?: string;
}

/** 계획 또는 구운 상태의 배치를 폐기한다. 부분 폐기면 잔량이 배치에 남는다. */
export interface WasteBatchParams {
  /** 배치 */
  batch: ObjectReference;
  /** 사유 */
  reason: "quality" | "expiry" | "damage" | "other";
  /** 폐기수량 */
  quantity?: number;
  /** 폐기일 */
  wastedOn?: string;
}

export const ACTION_NAMES = [
  "ApproveActionProposal",
  "ExpireActionProposal",
  "RejectActionProposal",
  "AdjustStoreStock",
  "CloseStore",
  "CompleteProductionPlan",
  "CreateProductionPlan",
  "ReceiveShipment",
  "RecordBatch",
  "ShipBatch",
  "StartProductionPlan",
  "UpsertProduct",
  "UpsertStore",
  "WasteBatch",
] as const;
export type ActionName = (typeof ACTION_NAMES)[number];

export interface ActionParamsByName {
  ApproveActionProposal: ApproveActionProposalParams;
  ExpireActionProposal: ExpireActionProposalParams;
  RejectActionProposal: RejectActionProposalParams;
  AdjustStoreStock: AdjustStoreStockParams;
  CloseStore: CloseStoreParams;
  CompleteProductionPlan: CompleteProductionPlanParams;
  CreateProductionPlan: CreateProductionPlanParams;
  ReceiveShipment: ReceiveShipmentParams;
  RecordBatch: RecordBatchParams;
  ShipBatch: ShipBatchParams;
  StartProductionPlan: StartProductionPlanParams;
  UpsertProduct: UpsertProductParams;
  UpsertStore: UpsertStoreParams;
  WasteBatch: WasteBatchParams;
}
