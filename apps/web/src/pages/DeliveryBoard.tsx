import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import type { Delivery, DeliveryStop, DeliveryStopProperties, Depot, Driver } from '../generated';
import { api } from '../generated';
import { ObjectTable } from '../components/ObjectTable';
import { StatusTag } from '../components/StatusTag';
import { ViolationBanner } from '../components/ViolationBanner';
import { number, shortTime } from '../lib/format';
import type { Violation } from '../generated';

export function DeliveryBoard() {
  const queryClient = useQueryClient();
  const today = new Date().toISOString().slice(0, 10);
  const [date, setDate] = useState(today);
  const [depotRid, setDepotRid] = useState('');
  const [selectedDelivery, setSelectedDelivery] = useState<string | null>(null);
  const [violations, setViolations] = useState<Violation[]>([]);
  const [notice, setNotice] = useState<string | null>(null);

  const depots = useQuery({
    queryKey: ['depots'],
    queryFn: () => api.search<Depot>('Depot', { pageSize: 50 }),
  });

  const deliveries = useQuery({
    queryKey: ['deliveries', date],
    queryFn: () =>
      api.search<Delivery>('Delivery', {
        filter: { field: 'deliveryDate', op: 'eq', value: date },
        orderBy: { deliveryNo: 'asc' },
        pageSize: 100,
      }),
  });

  const drivers = useQuery({
    queryKey: ['drivers'],
    queryFn: () => api.search<Driver>('Driver', { pageSize: 200 }),
  });
  const driverName = new Map((drivers.data?.data ?? []).map((driver) => [driver.rid, driver.properties.name]));

  const stops = useQuery({
    queryKey: ['stops', selectedDelivery],
    queryFn: () =>
      api.search<DeliveryStop>('DeliveryStop', {
        filter: { field: 'deliveryRid', op: 'eq', value: selectedDelivery },
        orderBy: { sequence: 'asc' },
        pageSize: 100,
      }),
    enabled: Boolean(selectedDelivery),
  });

  const plan = useMutation({
    mutationFn: () =>
      api.apply(
        'PlanDeliveries',
        { deliveryDate: date, depot: { objectType: 'Depot', rid: depotRid } },
        `plan-${date}-${Date.now()}`,
      ),
    onSuccess: (result) => {
      if (!result.success) {
        const details = result.error?.details as { violations?: Violation[] } | undefined;
        setViolations(details?.violations ?? [{ code: 'error', path: '', message: result.error?.message ?? '', severity: 'error' }]);
        setNotice(null);
        return;
      }
      const created = result.data.data?.created as Record<string, string[]> | undefined;
      setViolations([]);
      setNotice(`배송 ${created?.Delivery?.length ?? 0}건, 정류장 ${created?.DeliveryStop?.length ?? 0}개를 생성했습니다.`);
      void queryClient.invalidateQueries({ queryKey: ['deliveries'] });
    },
  });

  const completeStop = useMutation({
    mutationFn: (stop: DeliveryStop) =>
      api.apply('CompleteStop', {
        stop: { objectType: 'DeliveryStop', rid: stop.rid },
        actualCases: stop.properties.plannedCases ?? 0,
      }),
    onSuccess: (result) => {
      if (!result.success) {
        setNotice(result.error?.message ?? '납품 완료에 실패했습니다.');
        return;
      }
      setNotice('납품 완료 — 판매계산서가 발행되었습니다.');
      void queryClient.invalidateQueries({ queryKey: ['stops', selectedDelivery] });
      void queryClient.invalidateQueries({ queryKey: ['deliveries'] });
    },
  });

  const rows = deliveries.data?.data ?? [];

  return (
    <>
      <div className="page-head">
        <div>
          <h1>배송 보드</h1>
          <p>확정 발주를 배송 요일 기준으로 묶어 동선을 만들고, 정류장 단위로 납품을 마감합니다.</p>
        </div>
      </div>

      {notice && <div className="banner ok">{notice}</div>}
      <ViolationBanner violations={violations} />

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="grid" style={{ gridTemplateColumns: '160px 1frauto auto', alignItems: 'end', gap: 12 }}>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>배송일</label>
            <input type="date" value={date} onChange={(event) => setDate(event.target.value)} />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>창고</label>
            <select value={depotRid} onChange={(event) => setDepotRid(event.target.value)}>
              <option value="">선택하세요</option>
              {(depots.data?.data ?? []).map((depot) => (
                <option key={depot.rid} value={depot.rid}>
                  {depot.properties.name} ({depot.properties.region})
                </option>
              ))}
            </select>
          </div>
          <button
            className="primary"
            disabled={!depotRid || plan.isPending}
            onClick={() => plan.mutate()}
            style={{ alignSelf: 'end', marginBottom: 12 }}
          >
            배차 계획 생성
          </button>
        </div>
      </div>

      <ObjectTable
        rows={rows}
        rowKey={(row) => row.rid}
        onRowClick={(row) => setSelectedDelivery(row.rid)}
        empty="해당 날짜에 생성된 배송이 없습니다. 배차 계획을 생성해 보세요."
        columns={[
          { key: 'no', header: '배송번호', render: (row) => <span className="mono">{row.properties.deliveryNo}</span> },
          { key: 'driver', header: '기사', render: (row) => driverName.get(row.properties.driverRid ?? '') ?? '-' },
          { key: 'stops', header: '정류장', align: 'right', render: (row) => number(row.properties.totalStops) },
          { key: 'cases', header: '케이스', align: 'right', render: (row) => number(row.properties.totalCases) },
          { key: 'km', header: '거리', align: 'right', render: (row) => `${row.properties.plannedDistanceKm ?? '-'} km` },
          { key: 'status', header: '상태', render: (row) => <StatusTag value={row.properties.status} /> },
        ]}
      />

      {selectedDelivery && (
        <>
          <h2 style={{ fontSize: 15, margin: '24px 0 10px' }}>정류장</h2>
          <ObjectTable
            rows={stops.data?.data ?? []}
            rowKey={(row) => row.rid}
            empty={stops.isLoading ? '불러오는 중…' : '정류장이 없습니다.'}
            columns={[
              { key: 'seq', header: '순번', align: 'right', render: (row) => row.properties.sequence },
              {
                key: 'outlet',
                header: '거래처',
                render: (row) => (row.properties as DeliveryStopProperties & { outletRid?: string }).outletRid?.slice(-8) ?? '-',
              },
              { key: 'planned', header: '계획도착', render: (row) => shortTime(row.properties.plannedAt) },
              { key: 'cases', header: '계획', align: 'right', render: (row) => number(row.properties.plannedCases) },
              { key: 'actual', header: '실제', align: 'right', render: (row) => number(row.properties.actualCases) },
              { key: 'status', header: '상태', render: (row) => <StatusTag value={row.properties.status} /> },
              {
                key: 'action',
                header: '',
                render: (row) =>
                  row.properties.status === 'planned' || row.properties.status === 'arrived' ? (
                    <button className="ghost" onClick={() => completeStop.mutate(row)} disabled={completeStop.isPending}>
                      납품 완료
                    </button>
                  ) : null,
              },
            ]}
          />
        </>
      )}
    </>
  );
}
