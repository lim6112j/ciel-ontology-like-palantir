// GENERATED FILE — do not edit by hand.
// Regenerate with: uv run ontology export-web
export const dispatchAgent = {
  apiName: "dispatchAgent",
  displayName: "배송 배차 에이전트",
  kind: "dispatch",
  description: "확정 발주와 가용 자원을 확인해 배송 계획과 재배정을 제안한다.",
} as const;

export const exceptionAgent = {
  apiName: "exceptionAgent",
  displayName: "배송 예외 처리 에이전트",
  kind: "exception",
  description: "결정적 함수가 찾아낸 지연·실패·과적·미배정 문제에 대한 대응을 제안한다.",
} as const;

export const opsCopilotAgent = {
  apiName: "opsCopilotAgent",
  displayName: "운영 코파일럿",
  kind: "copilot",
  description: "읽기 전용으로 현황을 분석하고 고객 확인 메시지·기사 브리핑 초안을 작성한다.",
} as const;

export const orderIntakeAgent = {
  apiName: "orderIntakeAgent",
  displayName: "발주 접수 에이전트",
  kind: "intake",
  description: "영업사원의 자유 텍스트 발주를 해석해 발주 생성·제출을 제안한다.",
} as const;

export const AGENTS = [
  dispatchAgent,
  exceptionAgent,
  opsCopilotAgent,
  orderIntakeAgent,
] as const;
