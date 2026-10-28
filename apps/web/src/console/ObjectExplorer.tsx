import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { ObjectTable, type Column } from '../components/ObjectTable';
import type { DomainApi, ObjectTypeDetail, ObjectTypeSummary, OntologyObject } from './api';

const PAGE_SIZE = 25;

interface Props {
  api: DomainApi;
  domainName: string;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export function ObjectExplorer({ api, domainName }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  const [page, setPage] = useState(0);

  const types = useQuery({
    queryKey: [domainName, 'objectTypes'],
    queryFn: () => api.objectTypes(),
  });
  const objectTypes = ((types.data?.data as ObjectTypeSummary[]) ?? []).filter(
    (objectType) => !objectType.internal,
  );
  const active = selected ?? objectTypes[0]?.apiName ?? null;

  const detail = useQuery({
    queryKey: [domainName, 'objectType', active],
    queryFn: () => api.objectType(active as string),
    enabled: active !== null,
  });
  const objectTypeDetail = detail.data?.data as ObjectTypeDetail | undefined;

  const rows = useQuery({
    queryKey: [domainName, 'objects', active, page],
    queryFn: () =>
      api.search<OntologyObject>(active as string, { pageSize: PAGE_SIZE, pageToken: page }),
    enabled: active !== null,
  });
  const objects = (rows.data?.data as OntologyObject[]) ?? [];
  const total = Number((rows.data?.meta as { total?: number } | undefined)?.total ?? 0);

  const properties = objectTypeDetail?.properties ?? {};
  // Show a few identifying columns rather than every property.
  const columns: Column<OntologyObject>[] = Object.values(properties)
    .slice(0, 5)
    .map((prop) => ({
      key: prop.apiName,
      header: prop.displayName || prop.apiName,
      render: (row: OntologyObject) => formatValue(row.properties[prop.apiName]),
    }));

  const selectType = (apiName: string) => {
    setSelected(apiName);
    setPage(0);
  };

  const lastPage = Math.max(0, Math.ceil(total / PAGE_SIZE) - 1);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>객체 탐색기</h1>
          <p>이 도메인의 객체 타입을 골라 실제 저장된 객체를 조회합니다. 읽기 전용입니다.</p>
        </div>
      </div>

      <div className="tabs" style={{ flexWrap: 'wrap' }}>
        {objectTypes.map((objectType) => (
          <button
            key={objectType.apiName}
            className={active === objectType.apiName ? 'active' : ''}
            onClick={() => selectType(objectType.apiName)}
          >
            {objectType.displayName} ({objectType.apiName})
          </button>
        ))}
        {objectTypes.length === 0 && !types.isLoading && (
          <span className="muted">조회할 객체 타입이 없습니다.</span>
        )}
      </div>

      {active && (
        <>
          <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
            {objectTypeDetail?.description ?? '설명 없음'} · 총 {total.toLocaleString()}건
          </div>
          {rows.isError && (
            <div className="banner err">객체를 불러오지 못했습니다: {String(rows.error)}</div>
          )}
          <ObjectTable
            rows={objects}
            columns={
              columns.length > 0
                ? columns
                : [{ key: 'rid', header: 'RID', render: (row: OntologyObject) => row.rid }]
            }
            rowKey={(row) => row.rid}
            empty="저장된 객체가 없습니다."
          />
          <div style={{ display: 'flex', gap: 8, marginTop: 12, alignItems: 'center' }}>
            <button disabled={page === 0} onClick={() => setPage((value) => Math.max(0, value - 1))}>
              이전
            </button>
            <span className="muted" style={{ fontSize: 12 }}>
              {page + 1} / {lastPage + 1}
            </span>
            <button disabled={page >= lastPage} onClick={() => setPage((value) => value + 1)}>
              다음
            </button>
          </div>
        </>
      )}
    </>
  );
}
