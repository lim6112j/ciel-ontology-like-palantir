import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { StatusTag } from '../components/StatusTag';
import { ViolationBanner } from '../components/ViolationBanner';
import type { DomainApi, Violation } from './api';

interface Proposal {
  rid: string;
  properties: {
    proposalNo: string;
    actionType: string;
    rationale: string;
    confidence?: number;
    status: string;
    violations?: Violation[] | null;
    params?: Record<string, unknown>;
    decidedParams?: Record<string, unknown> | null;
    targetObjectType?: string;
    targetRid?: string;
    approvedBy?: string;
  };
}

const STATUS_TABS = [
  { key: 'proposed', label: '검토 대기' },
  { key: 'approved', label: '승인됨' },
  { key: 'rejected', label: '거절됨' },
  { key: '', label: '전체' },
];

interface Props {
  api: DomainApi;
  domainName: string;
  assistantPath: string;
}

export function ProposalInbox({ api, domainName, assistantPath }: Props) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState('proposed');
  const [editing, setEditing] = useState<string | null>(null);
  const [editedParams, setEditedParams] = useState('');
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const proposals = useQuery({
    queryKey: [domainName, 'proposals', status],
    queryFn: () => api.proposals(status || undefined),
  });

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: [domainName] });
  };

  const approve = useMutation({
    mutationFn: ({ proposal, params }: { proposal: Proposal; params?: Record<string, unknown> }) =>
      api.apply(
        'ApproveActionProposal',
        {
          proposal: { objectType: 'ActionProposal', rid: proposal.rid },
          approvedParams: params,
        },
        `approve-${proposal.rid}`,
      ),
    onSuccess: (result) => {
      if (!result.success) {
        setError(result.error?.message ?? '승인에 실패했습니다.');
        return;
      }
      setError(null);
      setNotice('승인되어 액션이 실행되었습니다.');
      setEditing(null);
      refresh();
    },
  });

  const reject = useMutation({
    mutationFn: (proposal: Proposal) =>
      api.apply('RejectActionProposal', {
        proposal: { objectType: 'ActionProposal', rid: proposal.rid },
        reason: '운영자 검토 후 거절',
      }),
    onSuccess: () => {
      setNotice('제안을 거절했습니다.');
      refresh();
    },
  });

  const rows = (proposals.data?.data ?? []) as Proposal[];

  return (
    <>
      <div className="page-head">
        <div>
          <h1>제안 인박스</h1>
          <p>
            에이전트는 데이터를 직접 변경할 수 없습니다. 승인하는 순간에만 액션이 검증·감사 경로를
            통과해 실행됩니다.
          </p>
        </div>
      </div>

      {notice && <div className="banner ok">{notice}</div>}
      {error && <div className="banner error">{error}</div>}

      <div className="tabs">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.key || 'all'}
            className={tab.key === status ? 'active' : ''}
            onClick={() => setStatus(tab.key)}
          >
            {tab.label}
          </button>
        ))}
        <span className="muted" style={{ marginLeft: 'auto', alignSelf: 'center', fontSize: 12 }}>
          {rows.length}건
        </span>
      </div>

      {rows.length === 0 && (
        <div className="empty">
          검토할 제안이 없습니다.{' '}
          <a href={assistantPath} style={{ color: 'var(--accent)' }}>
            운영 어시스턴트
          </a>
          에서 에이전트를 실행해 보세요.
        </div>
      )}

      <div className="grid" style={{ gap: 12 }}>
        {rows.map((proposal) => {
          const violations = proposal.properties.violations ?? [];
          return (
            <article className="proposal" key={proposal.rid}>
              <header>
                <div>
                  <h3>
                    {proposal.properties.actionType}{' '}
                    <span className="muted mono" style={{ fontSize: 11.5 }}>
                      {proposal.properties.proposalNo}
                    </span>
                  </h3>
                  <div className="muted" style={{ fontSize: 12 }}>
                    신뢰도 {Math.round((proposal.properties.confidence ?? 0) * 100)}% ·{' '}
                    {proposal.properties.targetObjectType ?? '대상 미지정'}
                  </div>
                </div>
                <StatusTag value={proposal.properties.status} />
              </header>

              <p className="rationale">{proposal.properties.rationale}</p>

              {violations.length > 0 && <ViolationBanner violations={violations} />}

              {proposal.properties.status === 'approved' &&
                proposal.properties.decidedParams != null &&
                JSON.stringify(proposal.properties.decidedParams) !==
                  JSON.stringify(proposal.properties.params) && (
                  <div className="banner" style={{ padding: '6px 10px', fontSize: 12 }}>
                    승인 시 파라미터가 수정되어 실행되었습니다. 아래는 확정값입니다.
                  </div>
                )}

              {editing === proposal.rid ? (
                <>
                  <textarea
                    value={editedParams}
                    onChange={(event) => setEditedParams(event.target.value)}
                    style={{
                      width: '100%',
                      minHeight: 140,
                      background: 'var(--bg)',
                      border: '1px solid var(--border)',
                      borderRadius: 8,
                      padding: 10,
                      fontFamily: 'var(--mono)',
                      fontSize: 12,
                    }}
                  />
                  <div className="actions" style={{ marginTop: 8 }}>
                    <button
                      className="primary"
                      onClick={() =>
                        approve.mutate({
                          proposal,
                          params: JSON.parse(editedParams) as Record<string, unknown>,
                        })
                      }
                      disabled={approve.isPending}
                    >
                      수정 후 승인
                    </button>
                    <button className="ghost" onClick={() => setEditing(null)}>
                      취소
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <pre>
                    {JSON.stringify(
                      proposal.properties.status === 'approved' &&
                        proposal.properties.decidedParams
                        ? proposal.properties.decidedParams
                        : (proposal.properties.params ?? {}),
                      null,
                      2,
                    )}
                  </pre>
                  {proposal.properties.status === 'proposed' && (
                    <div className="actions" style={{ marginTop: 10 }}>
                      <button
                        className="primary"
                        onClick={() => approve.mutate({ proposal })}
                        disabled={approve.isPending}
                      >
                        승인 후 실행
                      </button>
                      <button
                        className="ghost"
                        onClick={() => {
                          setEditing(proposal.rid);
                          setEditedParams(JSON.stringify(proposal.properties.params ?? {}, null, 2));
                        }}
                      >
                        수정
                      </button>
                      <button
                        className="danger"
                        onClick={() => reject.mutate(proposal)}
                        disabled={reject.isPending}
                      >
                        거절
                      </button>
                    </div>
                  )}
                </>
              )}
            </article>
          );
        })}
      </div>
    </>
  );
}
