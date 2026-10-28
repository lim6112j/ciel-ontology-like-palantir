import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import type { Outlet, Product, Violation } from '../../../generated/liquor';
import { api } from '../../../generated/liquor';
import { ViolationBanner } from '../../../components/ViolationBanner';
import { won } from '../../../lib/format';

interface Line {
  productRid: string;
  cases: number;
}

export function OrderComposer() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [outletRid, setOutletRid] = useState('');
  const [orderDate, setOrderDate] = useState(new Date().toISOString().slice(0, 10));
  const [deliveryDate, setDeliveryDate] = useState(
    new Date(Date.now() + 86400000).toISOString().slice(0, 10),
  );
  const [lines, setLines] = useState<Line[]>([{ productRid: '', cases: 1 }]);
  const [violations, setViolations] = useState<Violation[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  const outlets = useQuery({
    queryKey: ['outlets-order'],
    queryFn: () =>
      api.search<Outlet>('Outlet', {
        filter: { field: 'status', op: 'eq', value: 'active' },
        orderBy: { name: 'asc' },
        pageSize: 500,
      }),
  });
  const products = useQuery({
    queryKey: ['products'],
    queryFn: () =>
      api.search<Product>('Product', {
        filter: { field: 'active', op: 'eq', value: true },
        orderBy: { name: 'asc' },
        pageSize: 200,
      }),
  });

  const productList = products.data?.data ?? [];
  const productByRid = useMemo(
    () => new Map(productList.map((product) => [product.rid, product])),
    [productList],
  );

  const params = {
    outlet: outletRid ? { objectType: 'Outlet', rid: outletRid } : null,
    orderDate,
    requestedDeliveryDate: deliveryDate,
    channel: 'app',
    lines: lines
      .filter((line) => line.productRid)
      .map((line) => ({ productRid: line.productRid, cases: line.cases })),
  };

  const estimate = lines.reduce((sum, line) => {
    const product = productByRid.get(line.productRid);
    return sum + (product ? (product.properties.casePrice ?? 0) * line.cases : 0);
  }, 0);

  const validate = useMutation({
    mutationFn: () => api.validate('CreateSalesOrder', params),
    onSuccess: (result) => setViolations(result.data.violations ?? []),
  });

  const create = useMutation({
    mutationFn: () => api.apply('CreateSalesOrder', params, `order-${Date.now()}`),
    onSuccess: (result) => {
      if (!result.success) {
        const details = (result.error?.details ?? {}) as { violations?: Violation[] };
        setViolations(
          details.violations ?? [
            { code: 'error', path: '', message: result.error?.message ?? '', severity: 'error' },
          ],
        );
        return;
      }
      const created = (result.data.data?.created as Record<string, string[]> | undefined)?.SalesOrder ?? [];
      const orderRid = created[0];
      setViolations([]);
      if (orderRid) {
        const submit = api.apply('SubmitSalesOrder', { order: { objectType: 'SalesOrder', rid: orderRid } });
        void submit.then(async (submitted) => {
          if (submitted.success) {
            setMessage('발주가 접수되었습니다. 확정 후 배차됩니다.');
            void queryClient.invalidateQueries({ queryKey: ['orders'] });
            setTimeout(() => navigate('/orders'), 900);
          }
        });
      }
    },
  });

  return (
    <>
      <div className="page-head">
        <div>
          <h1>발주 접수</h1>
          <p>거래처와 제품을 고르면 액션 엔진이 합계·세액을 계산하고 검증합니다.</p>
        </div>
      </div>

      {message && <div className="banner ok">{message}</div>}
      <ViolationBanner violations={violations} />

      <div className="grid cols-2">
        <div className="card">
          <div className="field">
            <label>거래처</label>
            <select value={outletRid} onChange={(event) => setOutletRid(event.target.value)}>
              <option value="">선택하세요</option>
              {(outlets.data?.data ?? []).map((outlet) => (
                <option key={outlet.rid} value={outlet.rid}>
                  {outlet.properties.name} ({outlet.properties.outletNo})
                </option>
              ))}
            </select>
          </div>
          <div className="grid cols-2">
            <div className="field">
              <label>발주일</label>
              <input type="date" value={orderDate} onChange={(event) => setOrderDate(event.target.value)} />
            </div>
            <div className="field">
              <label>희망 납기일</label>
              <input type="date" value={deliveryDate} onChange={(event) => setDeliveryDate(event.target.value)} />
            </div>
          </div>

          <label className="muted" style={{ fontSize: 12 }}>발주 라인</label>
          {lines.map((line, index) => (
            <div key={index} className="grid" style={{ gridTemplateColumns: '1fr 90px 34px', gap: 8, marginTop: 6 }}>
              <select
                value={line.productRid}
                onChange={(event) =>
                  setLines((current) =>
                    current.map((entry, i) => (i === index ? { ...entry, productRid: event.target.value } : entry)),
                  )
                }
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 10px' }}
              >
                <option value="">제품 선택</option>
                {productList.map((product) => (
                  <option key={product.rid} value={product.rid}>
                    {product.properties.name} · {won(product.properties.casePrice)}/케이스
                  </option>
                ))}
              </select>
              <input
                type="number"
                min={1}
                value={line.cases}
                onChange={(event) =>
                  setLines((current) =>
                    current.map((entry, i) =>
                      i === index ? { ...entry, cases: Number(event.target.value) || 1 } : entry,
                    ),
                  )
                }
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 10px' }}
              />
              <button className="ghost" onClick={() => setLines((current) => current.filter((_, i) => i !== index))}>
                ✕
              </button>
            </div>
          ))}
          <div className="actions" style={{ marginTop: 10 }}>
            <button className="ghost" onClick={() => setLines((current) => [...current, { productRid: '', cases: 1 }])}>
              + 라인 추가
            </button>
          </div>
        </div>

        <div className="card">
          <div className="stat">
            <div className="label">예상 공급가</div>
            <div className="value">{won(estimate)}</div>
          </div>
          <p className="muted" style={{ fontSize: 12.5, marginTop: 8 }}>
            실제 금액·세액은 서버의 액션 함수가 계산합니다. 면세 제품(와인)은 세액에서 제외됩니다.
          </p>
          <div className="actions" style={{ marginTop: 16 }}>
            <button
              className="ghost"
              onClick={() => validate.mutate()}
              disabled={!outletRid || validate.isPending}
            >
              검증만 실행
            </button>
            <button
              className="primary"
              onClick={() => create.mutate()}
              disabled={!outletRid || create.isPending}
            >
              발주 접수
            </button>
          </div>
          <pre className="mono" style={{ background: 'var(--bg)', padding: 10, borderRadius: 8, overflow: 'auto', fontSize: 11.5, marginTop: 14 }}>
            {JSON.stringify(params, null, 2)}
          </pre>
        </div>
      </div>
    </>
  );
}
