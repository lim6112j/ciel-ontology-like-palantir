import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import type { ActionTypeSummary, AgentSummary, DomainApi, Envelope, ObjectTypeSummary } from './api';

interface Props {
  api: DomainApi;
  domainName: string;
}

type Tab = 'objects' | 'actions' | 'agents';

export function SchemaBrowser({ api, domainName }: Props) {
  const [tab, setTab] = useState<Tab>('objects');

  const objects = useQuery({ queryKey: [domainName, 'ontology-objects'], queryFn: () => api.objectTypes() });
  const actions = useQuery({ queryKey: [domainName, 'ontology-actions'], queryFn: () => api.actionTypes() });
  const agents = useQuery({ queryKey: [domainName, 'ontology-agents'], queryFn: () => api.agents() });

  const objectTypes = (objects.data?.data as ObjectTypeSummary[]) ?? [];
  const actionTypes = (actions.data as Envelope<ActionTypeSummary[]> | undefined)?.data ?? [];
  const agentList = (agents.data as Envelope<AgentSummary[]> | undefined)?.data ?? [];

  return (
    <>
      <div className="page-head">
        <div>
          <h1>스키마 브라우저</h1>
          <p>런타임이 실제로 사용하는 온톨로지 정의입니다. YAML이 단일 소스입니다.</p>
        </div>
      </div>

      <div className="tabs">
        <button className={tab === 'objects' ? 'active' : ''} onClick={() => setTab('objects')}>
          오브젝트 타입 {objectTypes.length}
        </button>
        <button className={tab === 'actions' ? 'active' : ''} onClick={() => setTab('actions')}>
          액션 타입 {actionTypes.length}
        </button>
        <button className={tab === 'agents' ? 'active' : ''} onClick={() => setTab('agents')}>
          에이전트 {agentList.length}
        </button>
      </div>

      {tab === 'objects' && (
        <div className="grid cols-2">
          {objectTypes.map((objectType) => (
            <div className="card" key={objectType.apiName}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <strong>{objectType.apiName}</strong>
                <span className="muted" style={{ fontSize: 12 }}>
                  {objectType.displayName}
                </span>
              </div>
              <p className="muted" style={{ fontSize: 12.5, margin: '6px 0' }}>
                {objectType.description ?? '설명 없음'}
              </p>
              <div className="muted" style={{ fontSize: 12 }}>
                PK <span className="mono">{objectType.primaryKey}</span> · 속성 {objectType.propertyCount}개
                {objectType.internal && (
                  <span className="tag" style={{ marginLeft: 8 }}>
                    internal
                  </span>
                )}
              </div>
              <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {objectType.links.map((link) => (
                  <span
                    key={link.apiName}
                    className="tag accent"
                    title={`${link.cardinality} ${link.targetType}`}
                  >
                    {link.apiName} → {link.targetType}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'actions' && (
        <div className="card" style={{ padding: 0 }}>
          <table>
            <thead>
              <tr>
                <th>액션</th>
                <th>설명</th>
                <th>구현</th>
                <th>에이전트 제안</th>
              </tr>
            </thead>
            <tbody>
              {actionTypes.map((action) => (
                <tr key={action.apiName}>
                  <td>
                    <strong>{action.apiName}</strong>
                    <div className="muted" style={{ fontSize: 11.5 }}>
                      {action.displayName}
                    </div>
                  </td>
                  <td className="muted">{action.description ?? '-'}</td>
                  <td>
                    {action.functionBacked ? (
                      <span className="tag accent">함수 기반</span>
                    ) : (
                      <span className="tag">선언형</span>
                    )}
                  </td>
                  <td>
                    {action.agentProposable ? <span className="tag ok">가능</span> : <span className="tag">불가</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'agents' && (
        <div className="grid cols-2">
          {agentList.length === 0 && <div className="empty">이 도메인에는 에이전트가 없습니다.</div>}
          {agentList.map((agent) => (
            <div className="card" key={agent.apiName}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <strong>{agent.displayName}</strong>
                <span className="tag">{agent.kind}</span>
              </div>
              <div className="mono muted" style={{ fontSize: 11.5, marginTop: 4 }}>
                {agent.apiName}
              </div>
              <div style={{ marginTop: 10, fontSize: 12.5 }}>
                <div className="muted">제안 가능 액션</div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                  {agent.allowedActionTypes.length === 0 ? (
                    <span className="tag">없음 (읽기 전용)</span>
                  ) : (
                    agent.allowedActionTypes.map((name) => (
                      <span key={name} className="tag accent">
                        {name}
                      </span>
                    ))
                  )}
                </div>
              </div>
              <div style={{ marginTop: 10, fontSize: 12.5 }}>
                <div className="muted">호출 가능 함수</div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                  {agent.allowedFunctions.map((name) => (
                    <span key={name} className="tag">
                      {name}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
