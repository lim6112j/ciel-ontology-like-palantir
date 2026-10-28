/** Liquor domain: adds the sales and dispatch screens on top of the shared console. */

import { DeliveryBoard } from './pages/DeliveryBoard';
import { OrderComposer } from './pages/OrderComposer';
import { Orders } from './pages/Orders';
import { OutletDetail } from './pages/OutletDetail';
import { Outlets } from './pages/Outlets';
import type { DomainOverrides } from '../index';

const overrides: DomainOverrides = {
  extraNav: [
    { to: 'outlets', label: '거래처' },
    { to: 'orders', label: '발주' },
    { to: 'orders/new', label: '발주 접수' },
    { to: 'deliveries', label: '배송 보드' },
  ],
  extraRoutes: [
    { path: 'outlets', element: Outlets },
    { path: 'outlets/:rid', element: OutletDetail },
    { path: 'orders', element: Orders },
    { path: 'orders/new', element: OrderComposer },
    { path: 'deliveries', element: DeliveryBoard },
  ],
  agentPresets: [
    { text: '행복식당 소주 5박스 내일 배송으로 접수해줘', agent: 'orderIntakeAgent' },
    { text: '2026-10-27 배차 계획 세워줘', agent: 'dispatchAgent' },
    { text: '오늘 배송에서 문제가 있는 정류장 알려줘', agent: 'exceptionAgent' },
    { text: '이번 주 기사별 실적을 요약해줘', agent: 'opsCopilotAgent' },
  ],
};

export default overrides;
