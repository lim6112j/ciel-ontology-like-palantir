// GENERATED FILE — do not edit by hand.
// Regenerate with: uv run ontology export-web
export const bakeryOpsAgent = {
  apiName: "bakeryOpsAgent",
  displayName: "베이커리 운영 코파이럿",
  kind: "copilot",
  description: "읽기 전용으로 생산·재고·폐기 현황을 분석하고 보고 초안을 작성한다.",
} as const;

export const batchPlannerAgent = {
  apiName: "batchPlannerAgent",
  displayName: "생산 계획 에이전트",
  kind: "dispatch",
  description: "소비기한 임박 배치와 매장 재고를 보고 생산계획·출하·폐기를 제안한다.",
} as const;

export const AGENTS = [
  bakeryOpsAgent,
  batchPlannerAgent,
] as const;
