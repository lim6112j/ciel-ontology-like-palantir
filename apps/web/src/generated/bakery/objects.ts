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

export const OBJECT_TYPE_NAMES = [
  "ActionProposal",
  "AgentRun",
  "Batch",
  "Product",
  "Store",
] as const;
export type ObjectTypeName = (typeof OBJECT_TYPE_NAMES)[number];

export type ObjectPropertiesByName = {
  ActionProposal: ActionProposalProperties;
  AgentRun: AgentRunProperties;
  Batch: BatchProperties;
  Product: ProductProperties;
  Store: StoreProperties;
};

export type ObjectByName = {
  ActionProposal: ActionProposal;
  AgentRun: AgentRun;
  Batch: Batch;
  Product: Product;
  Store: Store;
};
