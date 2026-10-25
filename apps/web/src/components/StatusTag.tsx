const STYLES: Record<string, string> = {
  active: 'ok',
  planned: 'accent',
  dispatched: 'accent',
  in_progress: 'warn',
  submitted: 'accent',
  confirmed: 'accent',
  completed: 'ok',
  fulfilled: 'ok',
  approved: 'ok',
  issued: 'ok',
  failed: 'danger',
  cancelled: 'danger',
  rejected: 'danger',
  expired: 'danger',
  suspended: 'warn',
  partially_fulfilled: 'warn',
  partially_completed: 'warn',
  proposed: 'warn',
  draft: '',
  closed: '',
};

const LABELS: Record<string, string> = {
  active: '운영중',
  suspended: '중지',
  closed: '폐업',
  draft: '초안',
  submitted: '제출',
  confirmed: '확정',
  partially_fulfilled: '부분충족',
  fulfilled: '충족',
  cancelled: '취소',
  planned: '계획',
  dispatched: '배차',
  in_progress: '진행중',
  completed: '완료',
  partially_completed: '부분완료',
  arrived: '도착',
  failed: '실패',
  issued: '발행',
  proposed: '제안됨',
  approved: '승인',
  rejected: '거절',
  expired: '만료',
  available: '가용',
  on_leave: '휴무',
  maintenance: '정비',
};

export function StatusTag({ value }: { value?: string | null }) {
  if (!value) return <span className="tag">-</span>;
  return <span className={`tag ${STYLES[value] ?? ''}`}>{LABELS[value] ?? value}</span>;
}
