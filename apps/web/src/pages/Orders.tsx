import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import type { Outlet, SalesOrder } from '../generated';
import { api } from '../generated';
import { ObjectTable } from '../components/ObjectTable';
import { StatusTag } from '../components/StatusTag';
import { number, shortTime, won } from '../lib/format';

const STATUS_TABS = [
  { key: 'confirmed', label: '확정' },
  { key: 'submitted', label: '제출' },
  { key: 'draft', label: '초안' },
  { key: 'all', label: '전체' },
];

export function Orders() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState('confirmed');
  const [page, setPage] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['orders', status, page],
    queryFn: () =>
      api.search<SalesOrder>('SalesOrder', {
        filter: status === 'all' ? undefined : { field: 'status', op: 'eq', value: status },
        orderBy: { orderDate: 'desc' },
        pageSize: 25,
        pageToken: page,
      }),
  });

  const outlets = useQuery({
    queryKey: ['outlets-lookup'],
    queryFn: () => api.search<Outlet>('Outlet', { pageSize: 500 }),
  });

  const outletName = new Map<string, string>();
  for (const outlet of outlets.data?.data ?? []) {
    outletName.set(outlet.rid, outlet.properties.name);
  }

  const confirm = useMutation({
    mutationFn: (order: SalesOrder) =>
      api.apply('ConfirmSalesOrder', { order: { objectType: 'SalesOrder', rid: order.rid } }),
    onSuccess: (result) => {
      if (!result.success) {
        setError(result.error?.message ?? '확정에 실패했습니다.');
        return;
      }
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ['orders'] });
    },
  });

  const rows = data?.data ?? [];
  const total = (data?.meta?.total as number | undefined) ?? 0;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>발주</h1>
          <p>제출된 발주를 확정하면 배차 대상이 됩니다.</p>
        </div>
      </div>

      {error && <div className="banner error">{error}</div>}

      <div className="tabs">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.key}
            className={tab.key === status ? 'active' : ''}
            onClick={() => {
              setStatus(tab.key);
              setPage(0);
            }}
          >
            {tab.label}
          </button>
        ))}
        <span className="muted" style={{ marginLeft: 'auto', alignSelf: 'center', fontSize: 12 }}>
          총 {total}건
        </span>
      </div>

      <ObjectTable
        rows={rows}
        rowKey={(row) => row.rid}
        empty={isLoading ? '불러오는 중…' : '발주가 없습니다.'}
        columns={[
          { key: 'no', header: '발주번호', render: (row) => <span className="mono">{row.properties.orderNo}</span> },
          {
            key: 'outlet',
            header: '거래처',
            render: (row) => outletName.get(row.properties.outletRid ?? '') ?? row.properties.outletRid?.slice(-6),
          },
          { key: 'date', header: '발주일', render: (row) => shortTime(row.properties.orderDate) },
          { key: 'due', header: '납기', render: (row) => shortTime(row.properties.requestedDeliveryDate) },
          { key: 'cases', header: '케이스', align: 'right', render: (row) => number(row.properties.totalCases) },
          { key: 'amount', header: '금액', align: 'right', render: (row) => won(row.properties.totalAmount) },
          { key: 'status', header: '상태', render: (row) => <StatusTag value={row.properties.status} /> },
          {
            key: 'action',
            header: '',
            render: (row) =>
              row.properties.status === 'submitted' ? (
                <button className="ghost" onClick={() => confirm.mutate(row)} disabled={confirm.isPending}>
                  확정
                </button>
              ) : null,
          },
        ]}
      />

      <div className="actions" style={{ marginTop: 14 }}>
        <button className="ghost" disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
          이전
        </button>
        <button className="ghost" disabled={(page + 1) * 25 >= total} onClick={() => setPage((p) => p + 1)}>
          다음
        </button>
      </div>
    </>
  );
}
