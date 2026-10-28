import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import type { Outlet } from '../../../generated/liquor';
import { api, type Envelope } from '../../../generated/liquor';
import { ObjectTable } from '../../../components/ObjectTable';
import { StatusTag } from '../../../components/StatusTag';
import { weekday } from '../../../lib/format';

interface Meta {
  total?: number;
}

const FILTERS = [
  { key: 'all', label: '전체', filter: undefined },
  { key: 'active', label: '운영중', filter: { field: 'status', op: 'eq', value: 'active' } },
  { key: 'suspended', label: '중지', filter: { field: 'status', op: 'eq', value: 'suspended' } },
];

export function Outlets() {
  const navigate = useNavigate();
  const [filterKey, setFilterKey] = useState('all');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);

  const active = FILTERS.find((entry) => entry.key === filterKey)!;
  const { data, isLoading } = useQuery({
    queryKey: ['outlets', filterKey, search, page],
    queryFn: () =>
      api.search<Outlet>('Outlet', {
        filter: search
          ? { and: [active.filter, { field: 'name', op: 'contains', value: search }].filter(Boolean) }
          : active.filter,
        orderBy: { name: 'asc' },
        pageSize: 25,
        pageToken: page,
      }) as Promise<Envelope<Outlet[]> & { meta: Meta }>,
  });

  const total = data?.meta?.total ?? 0;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>거래처</h1>
          <p>배송 요일과 담당 영업사원을 기준으로 발주가 발생합니다.</p>
        </div>
        <div className="actions">
          <input
            placeholder="거래처명 검색"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(0);
            }}
            style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 10px' }}
          />
        </div>
      </div>

      <div className="tabs">
        {FILTERS.map((entry) => (
          <button
            key={entry.key}
            className={entry.key === filterKey ? 'active' : ''}
            onClick={() => {
              setFilterKey(entry.key);
              setPage(0);
            }}
          >
            {entry.label}
          </button>
        ))}
        <span className="muted" style={{ marginLeft: 'auto', alignSelf: 'center', fontSize: 12 }}>
          총 {total}곳
        </span>
      </div>

      <ObjectTable
        rows={data?.data ?? []}
        rowKey={(row) => row.rid}
        onRowClick={(row) => navigate(`/outlets/${row.rid}`)}
        empty={isLoading ? '불러오는 중…' : '결과가 없습니다.'}
        columns={[
          { key: 'no', header: '코드', render: (row) => <span className="mono">{row.properties.outletNo}</span> },
          { key: 'name', header: '거래처명', render: (row) => row.properties.name },
          { key: 'type', header: '업태', render: (row) => row.properties.outletType },
          { key: 'day', header: '배송요일', render: (row) => weekday(row.properties.deliveryWeekday) },
          { key: 'window', header: '시간대', render: (row) => row.properties.deliveryWindow ?? '-' },
          { key: 'status', header: '상태', render: (row) => <StatusTag value={row.properties.status} /> },
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
