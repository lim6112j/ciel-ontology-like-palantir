const KRW = new Intl.NumberFormat('ko-KR');

export function won(value?: number | null): string {
  if (value === null || value === undefined) return '-';
  return `${KRW.format(value)}원`;
}

export function number(value?: number | null): string {
  if (value === null || value === undefined) return '-';
  return KRW.format(value);
}

const WEEKDAYS = ['월', '화', '수', '목', '금', '토', '일'];

export function weekday(value?: number | null): string {
  if (value === null || value === undefined) return '-';
  return WEEKDAYS[value] ?? String(value);
}

export function shortTime(value?: string | null): string {
  if (!value) return '-';
  return value.replace('T', ' ').slice(5, 16);
}

export function shortRid(rid?: string | null): string {
  if (!rid) return '-';
  const parts = rid.split('.');
  return `${parts[3] ?? ''}.${(parts[4] ?? '').slice(0, 6)}`;
}
