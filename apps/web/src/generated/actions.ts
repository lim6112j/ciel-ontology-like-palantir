// GENERATED FILE — do not edit by hand.
// Regenerate with: uv run ontology export-client --out apps/web/src/generated
import type { ObjectReference } from "./client";/** 초안 발주에 제품 라인을 추가하고 합계를 다시 계산한다. */
export interface AddOrderLineParams {
  /** 발주 */
  order: ObjectReference;
  /** 제품 */
  product: ObjectReference;
  /** 케이스 */
  cases: number;
}

/** 운영자가 제안을 승인하면 대상 액션이 동일한 검증·감사 경로로 실행된다. 운영자 승인 전용 액션이다. */
export interface ApproveActionProposalParams {
  /** 제안 */
  proposal: ObjectReference;
  /** 수정된파라미터 */
  approvedParams?: unknown;
  /** 승인메모 */
  note?: string;
}

/** 기사가 납품처에 도착했음을 기록한다. */
export interface ArriveAtStopParams {
  /** 정류장 */
  stop: ObjectReference;
}

/** 확정 전 발주를 취소한다. 배송이 시작된 발주는 취소할 수 없다. */
export interface CancelSalesOrderParams {
  /** 발주 */
  order: ObjectReference;
  /** 사유 */
  reason?: string;
}

/** 모든 정류장을 마친 배송을 완료 처리한다. 실패 정류장이 있으면 부분 완료가 된다. */
export interface CompleteDeliveryParams {
  /** 배송 */
  delivery: ObjectReference;
}

/** 납품을 완료하고 판매계산서를 발행하며 발주 상태를 갱신한다. */
export interface CompleteStopParams {
  /** 정류장 */
  stop: ObjectReference;
  /** 실제케이스 */
  actualCases: number;
}

/** 제출된 발주를 확정해 배차 대상으로 만든다. */
export interface ConfirmSalesOrderParams {
  /** 발주 */
  order: ObjectReference;
}

/** 거래처·영업사원·발주일과 라인을 받아 초안 발주와 라인을 함께 만든다. */
export interface CreateSalesOrderParams {
  /** 거래처 */
  outlet: ObjectReference;
  /** 영업사원 */
  salesRep?: ObjectReference;
  /** 발주일 */
  orderDate: string;
  /** 희망납기일 */
  requestedDeliveryDate?: string;
  /** 접수경로 */
  channel: "phone" | "message" | "app" | "agent";
  /** 라인 */
  lines: unknown;
  /** 비고 */
  note?: string;
}

/** 계획된 배송을 출발 준비 상태로 전이한다. */
export interface DispatchDeliveryParams {
  /** 배송 */
  delivery: ObjectReference;
}

/** 오래된 제안을 만료 처리한다. 만료된 제안은 승인할 수 없다. */
export interface ExpireActionProposalParams {
  /** 제안 */
  proposal: ObjectReference;
  /** 만료사유 */
  reason?: string;
}

/** 납품 실패 사유를 기록한다. 실패한 정류장은 재배차 대상이 된다. */
export interface FailStopParams {
  /** 정류장 */
  stop: ObjectReference;
  /** 실패사유 */
  reason: "영업중아님" | "재고없음" | "거래처요청" | "차량문제" | "주소오류" | "기타";
  /** 상세 */
  note?: string;
}

/** 지정 일자의 확정 발주로 배송·정류장을 생성한다. 요일·용량·거리 순회를 적용한다. */
export interface PlanDeliveriesParams {
  /** 배송일 */
  deliveryDate: string;
  /** 창고 */
  depot: ObjectReference;
  /** 차량당최대정류장 */
  maxStopsPerVehicle?: number;
}

/** 배송의 담당 기사·차량을 교체한다. */
export interface ReassignDriverParams {
  /** 배송 */
  delivery: ObjectReference;
  /** 새기사 */
  driver: ObjectReference;
  /** 새차량 */
  vehicle?: ObjectReference;
  /** 사유 */
  reason?: string;
}

/** 실패하거나 미완료된 정류장을 다른 배송으로 옮긴다. */
export interface ReassignStopParams {
  /** 정류장 */
  stop: ObjectReference;
  /** 대상배송 */
  targetDelivery: ObjectReference;
  /** 순번 */
  sequence?: number;
}

/** 신규 배송기사를 등록한다. */
export interface RegisterDriverParams {
  /** 사번 */
  employeeNo: string;
  /** 이름 */
  name: string;
  /** 고용형태 */
  employmentType: "직영" | "지입";
  /** 운전면허 */
  licenseType: "1종보통" | "1종대형" | "2종보통";
  /** 소속창고 */
  depot: ObjectReference;
  /** 연락처 */
  phone?: string;
}

/** 신규 배송차량을 등록한다. */
export interface RegisterVehicleParams {
  /** 차량번호 */
  plateNo: string;
  /** 차종 */
  vehicleType: "1톤탑차" | "1.4톤탑차" | "2.5톤탑차" | "5톤윙바디";
  /** 적재케이스 */
  capacityCases: number;
  /** 적재중량(kg) */
  capacityWeightKg: number;
  /** 소속창고 */
  depot: ObjectReference;
}

/** 운영자가 제안을 거절한다. 거절 사유는 이후 에이전트 개선 데이터로 남는다. */
export interface RejectActionProposalParams {
  /** 제안 */
  proposal: ObjectReference;
  /** 거절사유 */
  reason: string;
}

/** 초안 발주에서 라인을 제거하고 합계를 다시 계산한다. */
export interface RemoveOrderLineParams {
  /** 발주라인 */
  line: ObjectReference;
}

/** 기사의 가용·휴무·비활성 상태를 변경한다. */
export interface SetDriverAvailabilityParams {
  /** 기사 */
  driver: ObjectReference;
  /** 상태 */
  status: "available" | "on_leave" | "inactive";
}

/** 거래처의 정기 배송요일을 변경한다. */
export interface SetOutletDeliveryDayParams {
  /** 거래처 */
  outlet: ObjectReference;
  /** 배송요일 */
  deliveryWeekday: number;
}

/** 배송 계획을 출발 전에 수동으로 조정한다. */
export interface SetStopSequenceParams {
  /** 정류장 */
  stop: ObjectReference;
  /** 순번 */
  sequence: number;
}

/** 기사가 배송을 시작한다. 배송 상태와 기사 근무를 함께 갱신한다. */
export interface StartDeliveryParams {
  /** 배송 */
  delivery: ObjectReference;
}

/** 초안 발주를 제출 상태로 전이한다. 라인이 없으면 거부된다. */
export interface SubmitSalesOrderParams {
  /** 발주 */
  order: ObjectReference;
}

/** 요일별 상시 배송노선을 만들거나 수정한다. */
export interface UpsertDeliveryRouteParams {
  /** 노선코드 */
  routeCode: string;
  /** 노선명 */
  name: string;
  /** 요일 */
  weekday: number;
  /** 창고 */
  depot: ObjectReference;
  /** 담당영업사원 */
  salesRep?: ObjectReference;
}

/** 거래처를 신규 등록하거나 기존 거래처 정보를 갱신한다. */
export interface UpsertOutletParams {
  /** 거래처코드 */
  outletNo?: string;
  /** 거래처명 */
  name: string;
  /** 업태 */
  outletType: "소매점" | "일반음식점" | "유흥주점" | "편의점" | "마트" | "실수요자";
  /** 주소 */
  address?: string;
  /** 배송요일 */
  deliveryWeekday?: number;
  /** 담당창고 */
  depot?: ObjectReference;
  /** 담당영업사원 */
  salesRep?: ObjectReference;
}

export const ACTION_NAMES = [
  "AddOrderLine",
  "ApproveActionProposal",
  "ArriveAtStop",
  "CancelSalesOrder",
  "CompleteDelivery",
  "CompleteStop",
  "ConfirmSalesOrder",
  "CreateSalesOrder",
  "DispatchDelivery",
  "ExpireActionProposal",
  "FailStop",
  "PlanDeliveries",
  "ReassignDriver",
  "ReassignStop",
  "RegisterDriver",
  "RegisterVehicle",
  "RejectActionProposal",
  "RemoveOrderLine",
  "SetDriverAvailability",
  "SetOutletDeliveryDay",
  "SetStopSequence",
  "StartDelivery",
  "SubmitSalesOrder",
  "UpsertDeliveryRoute",
  "UpsertOutlet",
] as const;
export type ActionName = (typeof ACTION_NAMES)[number];

export interface ActionParamsByName {
  AddOrderLine: AddOrderLineParams;
  ApproveActionProposal: ApproveActionProposalParams;
  ArriveAtStop: ArriveAtStopParams;
  CancelSalesOrder: CancelSalesOrderParams;
  CompleteDelivery: CompleteDeliveryParams;
  CompleteStop: CompleteStopParams;
  ConfirmSalesOrder: ConfirmSalesOrderParams;
  CreateSalesOrder: CreateSalesOrderParams;
  DispatchDelivery: DispatchDeliveryParams;
  ExpireActionProposal: ExpireActionProposalParams;
  FailStop: FailStopParams;
  PlanDeliveries: PlanDeliveriesParams;
  ReassignDriver: ReassignDriverParams;
  ReassignStop: ReassignStopParams;
  RegisterDriver: RegisterDriverParams;
  RegisterVehicle: RegisterVehicleParams;
  RejectActionProposal: RejectActionProposalParams;
  RemoveOrderLine: RemoveOrderLineParams;
  SetDriverAvailability: SetDriverAvailabilityParams;
  SetOutletDeliveryDay: SetOutletDeliveryDayParams;
  SetStopSequence: SetStopSequenceParams;
  StartDelivery: StartDeliveryParams;
  SubmitSalesOrder: SubmitSalesOrderParams;
  UpsertDeliveryRoute: UpsertDeliveryRouteParams;
  UpsertOutlet: UpsertOutletParams;
}
