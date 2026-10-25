import type { ReactNode } from 'react';

export interface Column<T> {
  key: string;
  header: string;
  align?: 'left' | 'right';
  render: (row: T) => ReactNode;
}

interface Props<T> {
  rows: T[];
  columns: Column<T>[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  empty?: string;
}

export function ObjectTable<T>({ rows, columns, rowKey, onRowClick, empty }: Props<T>) {
  if (rows.length === 0) {
    return <div className="empty">{empty ?? '데이터가 없습니다.'}</div>;
  }
  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} style={column.align === 'right' ? { textAlign: 'right' } : undefined}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              style={onRowClick ? { cursor: 'pointer' } : undefined}
            >
              {columns.map((column) => (
                <td key={column.key} className={column.align === 'right' ? 'num' : undefined}>
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
