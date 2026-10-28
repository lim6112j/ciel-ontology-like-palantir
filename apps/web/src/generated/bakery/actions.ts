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

/** 운영 중인 매장을 휴업 상태로 전환한다. */
export interface CloseStoreParams {
  /** 매장 */
  store: ObjectReference;
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

export const ACTION_NAMES = [
  "ApproveActionProposal",
  "ExpireActionProposal",
  "RejectActionProposal",
  "CloseStore",
  "RecordBatch",
] as const;
export type ActionName = (typeof ACTION_NAMES)[number];

export interface ActionParamsByName {
  ApproveActionProposal: ApproveActionProposalParams;
  ExpireActionProposal: ExpireActionProposalParams;
  RejectActionProposal: RejectActionProposalParams;
  CloseStore: CloseStoreParams;
  RecordBatch: RecordBatchParams;
}
