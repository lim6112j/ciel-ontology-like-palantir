import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';

import type { Outlet, SalesOrder } from '../generated';
import { api } from '../generated';
import { ObjectTable } from '../components/ObjectTable';
import { StatusTag } from '../components/StatusTag';
import { number, shortTime, weekday, won } from '../lib/format';

export function OutletDetail() {
  const { rid = '' } = useParams();
  const queryClient = useQueryClient();

  const outlet = useQuery({
    queryKey: ['outlet', rid],
    queryFn: () => api.get<Outlet>('Outlet', rid),
  });

  const orders = useQuery({
    queryKey: ['outlet-orders', rid],
    queryFn: () => api.linked<SalesOrder>('Outlet', rid, 'orders'),
    enabled: Boolean(rid),
  });

  const ordersList = orders.data?.data ?? [];

  const setWeekday = useMutation({
    mutationFn: (day: number) =>
      api.apply('SetOutletDeliveryDay', { outlet: { objectType: 'Outlet', rid }, deliveryWeekday: day }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['outlet', rid] });
    },
  });

  const detail = outlet.data?.data;
  if (outlet.isLoading) return <div className="empty">불러오는 중…</div>;
  if (outlet.error || !detail) return <div className="banner error">거래처를 찾을 수 없습니다.</div>;

  const props = detail.properties;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>{props.name}</h1>
          <p>
            {props.outletNo} · {props.outletType} · {props.address ?? '주소 미등록'}
          </p>
        </div>
        <StatusTag value={props.status} />
      </div>

      <div className="grid cols-3" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="stat">
            <div className="label">정기 배송요일</div>
            <div className="value">{weekday(props.deliveryWeekday)}요일</div>
          </div>
          <div className="actions" style={{ marginTop: 10 }}>
            {[0, 1, 2, 3, 4, 5].map((day) => (
              <button key={day} className="ghost" onClick={() => setWeekday.mutate(day)} disabled={setWeekday.isPending}>
                {weekday(day)}
              </button>
            ))}
          </div>
        </div>
        <div className="card">
          <div className="stat">
            <div className="label">누적 발주</div>
            <div className="value">{ordersList.length}건</div>
          </div>
        </div>
        <div className="card">
          <div className="stat">
            <div className="label">누적 케이스</div>
            <div className="value">{number(ordersList.reduce((sum, o) => sum + (o.properties.totalCases ?? 0), 0))}</div>
          </div>
        </div>
      </div>

      <h2 style={{ fontSize: 15, margin: '22px 0 10px' }}>발주 이력</h2>
      <ObjectTable
        rows={ordersList.slice(0, 20)}
        rowKey={(row) => row.rid}
        empty="발주 이력이 없습니다."
        columns={[
          { key: 'no', header: '발주번호', render: (row) => <span className="mono">{row.properties.orderNo}</span> },
          { key: 'date', header: '발주일', render: (row) => shortTime(row.properties.orderDate) },
          { key: 'due', header: '납기', render: (row) => shortTime(row.properties.requestedDeliveryDate) },
          { key: 'cases', header: '케이스', align: 'right', render: (row) => number(row.properties.totalCases) },
          { key: 'amount', header: '금액', align: 'right', render: (row) => won(row.properties.totalAmount) },
          { key: 'status', header: '상태', render: (row) => <StatusTag value={row.properties.status} /> },
        ]}
      />
    </>
  );
}
