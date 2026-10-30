// GENERATED FILE — do not edit by hand.
// Regenerate with: uv run ontology export-web
export const brewPlannerAgent = {
  apiName: "brewPlannerAgent",
  displayName: "양조 계획 에이전트",
  kind: "dispatch",
  description: "발효·숙성 진행과 온도 이탈을 확인해 완료·조치·폐기·재양조를 제안한다.",
} as const;

export const breweryOpsAgent = {
  apiName: "breweryOpsAgent",
  displayName: "양조장 운영 코파이럿",
  kind: "copilot",
  description: "읽기 전용으로 양조·온도·재고·판매 현황을 분석하고 보고 초안을 작성한다.",
} as const;

export const salesIntakeAgent = {
  apiName: "salesIntakeAgent",
  displayName: "판매 접수 에이전트",
  kind: "intake",
  description: "판매처의 주문을 해석해 주문 생성·확정·출하를 제안한다.",
} as const;

export const AGENTS = [
  brewPlannerAgent,
  breweryOpsAgent,
  salesIntakeAgent,
] as const;
