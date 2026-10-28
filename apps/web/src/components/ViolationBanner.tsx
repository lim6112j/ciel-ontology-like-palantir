import type { Violation } from '../console/api';

export function ViolationBanner({ violations }: { violations: Violation[] }) {
  if (!violations.length) return null;
  return (
    <div className="violations">
      <strong>검증 실패</strong>
      <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
        {violations.map((violation, index) => (
          <li key={`${violation.code}-${index}`}>
            <span className="path">{violation.path || '-'}</span> {violation.message}
          </li>
        ))}
      </ul>
    </div>
  );
}
