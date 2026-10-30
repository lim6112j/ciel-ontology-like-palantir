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

/** 온도 이탈 배치의 목표온도를 탱크 조절범위 내에서 변경한다. */
export interface AdjustBatchTempParams {
  /** 배치 */
  batch: ObjectReference;
  /** 단계 */
  stage: "fermentation" | "aging";
  /** 새목표온도(°C) */
  targetTempC: number;
}

/** 재고 실사 차이 등으로 창고 재고를 수동 조정한다. 에이전트가 제안할 수 없다. */
export interface AdjustWarehouseStockParams {
  /** 재고 */
  stock: ObjectReference;
  /** 조정량 */
  delta: number;
}

/** 작성 중이거나 확정된 판매주문을 취소한다. */
export interface CancelSalesOrderParams {
  /** 주문 */
  order: ObjectReference;
}

/** 숙성 중 배치를 병입해 소비기한을 부여하고 창고 재고를 생성한다. */
export interface CompleteAgingParams {
  /** 배치 */
  batch: ObjectReference;
  /** 병입일 */
  bottledOn?: string;
  /** 병입수량(병) */
  bottledQty?: number;
}

/** 발효 중 배치를 숙성 단계로 전환한다. */
export interface CompleteFermentationParams {
  /** 배치 */
  batch: ObjectReference;
  /** 발효완료일 */
  fermentedOn?: string;
}

/** 작성 중인 판매주문을 확정한다. */
export interface ConfirmSalesOrderParams {
  /** 주문 */
  order: ObjectReference;
}

/** 제품·양조일·양조량으로 배치를 생성하고 파생일과 목표온도를 계산한다. */
export interface CreateBatchParams {
  /** 제품 */
  product: ObjectReference;
  /** 탱크 */
  tank?: ObjectReference;
  /** 양조일 */
  brewDate: string;
  /** 양조량(L) */
  volumeL: number;
  /** 투입원자재 */
  materials?: unknown;
}

/** 판매처 주문을 라인과 함께 생성하고 합계를 계산한다. */
export interface CreateSalesOrderParams {
  /** 판매처 */
  customer: ObjectReference;
  /** 주문일 */
  orderDate: string;
  /** 주문라인 */
  lines: unknown;
  /** 비고 */
  note?: string;
}

/** 배송 중 출하를 입고 처리하고 판매처 재고를 올린다. */
export interface ReceiveShipmentParams {
  /** 출하 */
  shipment: ObjectReference;
  /** 입고일 */
  receivedOn?: string;
}

/** 배치의 발효·숙성 온도를 기록하고 목표범위 대비 허용여부를 판정한다. */
export interface RecordTempReadingParams {
  /** 배치 */
  batch: ObjectReference;
  /** 측정온도(°C) */
  tempC: number;
  /** 단계 */
  stage: "fermentation" | "aging";
  /** 측정시각 */
  recordedAt?: string;
}

/** 원자재 입고분을 현재재고에 더한다. 에이전트가 제안할 수 없다. */
export interface RestockMaterialParams {
  /** 원자재 */
  material: ObjectReference;
  /** 입고량 */
  amount: number;
  /** 입고일 */
  restockedOn?: string;
}

/** 병입 완료 배치를 판매처로 출하하고 창고 재고를 차감한다. */
export interface ShipBatchParams {
  /** 배치 */
  batch: ObjectReference;
  /** 판매처 */
  customer: ObjectReference;
  /** 주문 */
  order?: ObjectReference;
  /** 출하수량(병) */
  quantity?: number;
  /** 출하일 */
  shipDate?: string;
}

/** 판매처번호로 판매처를 신규 등록하거나 기존 정보를 갱신한다. */
export interface UpsertCustomerParams {
  /** 판매처번호 */
  customerNo: string;
  /** 명칭 */
  name: string;
  /** 유형 */
  type: "유흥주점" | "편의점" | "대형마트" | "온라인" | "직영점";
  /** 지역 */
  region?: string;
}

/** SKU로 제품을 신규 등록하거나 기존 제품 정보를 갱신한다. */
export interface UpsertProductParams {
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
  active?: boolean;
}

/** 배치를 전부 또는 일부 폐기하고 폐기기록을 남긴다. */
export interface WasteBatchParams {
  /** 배치 */
  batch: ObjectReference;
  /** 사유 */
  reason: "quality" | "expiry" | "damage" | "other";
  /** 폐기수량(병) */
  quantity?: number;
  /** 폐기일 */
  wastedOn?: string;
}

export const ACTION_NAMES = [
  "ApproveActionProposal",
  "ExpireActionProposal",
  "RejectActionProposal",
  "AdjustBatchTemp",
  "AdjustWarehouseStock",
  "CancelSalesOrder",
  "CompleteAging",
  "CompleteFermentation",
  "ConfirmSalesOrder",
  "CreateBatch",
  "CreateSalesOrder",
  "ReceiveShipment",
  "RecordTempReading",
  "RestockMaterial",
  "ShipBatch",
  "UpsertCustomer",
  "UpsertProduct",
  "WasteBatch",
] as const;
export type ActionName = (typeof ACTION_NAMES)[number];

export interface ActionParamsByName {
  ApproveActionProposal: ApproveActionProposalParams;
  ExpireActionProposal: ExpireActionProposalParams;
  RejectActionProposal: RejectActionProposalParams;
  AdjustBatchTemp: AdjustBatchTempParams;
  AdjustWarehouseStock: AdjustWarehouseStockParams;
  CancelSalesOrder: CancelSalesOrderParams;
  CompleteAging: CompleteAgingParams;
  CompleteFermentation: CompleteFermentationParams;
  ConfirmSalesOrder: ConfirmSalesOrderParams;
  CreateBatch: CreateBatchParams;
  CreateSalesOrder: CreateSalesOrderParams;
  ReceiveShipment: ReceiveShipmentParams;
  RecordTempReading: RecordTempReadingParams;
  RestockMaterial: RestockMaterialParams;
  ShipBatch: ShipBatchParams;
  UpsertCustomer: UpsertCustomerParams;
  UpsertProduct: UpsertProductParams;
  WasteBatch: WasteBatchParams;
}
