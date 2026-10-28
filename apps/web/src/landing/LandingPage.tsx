import { Link } from 'react-router-dom';

import { DOMAINS } from '../generated/domains';

export function LandingPage() {
  return (
    <div className="landing">
      <header className="landing-head">
        <h1>온톨로지 콘솔</h1>
        <p className="muted">
          도메인을 선택하세요. 각 도메인은 독립된 스키마·데이터·에이전트를 사용합니다.
        </p>
      </header>

      {DOMAINS.length === 0 ? (
        <div className="empty">
          활성화된 도메인이 없습니다. <code>uv run ontology export-web</code>을 실행하세요.
        </div>
      ) : (
        <div className="landing-grid">
          {DOMAINS.map((domain) => (
            <Link key={domain.apiName} to={`/${domain.apiName}`} className="domain-card">
              <div className="domain-card-head">
                <h2>{domain.displayName}</h2>
                <span className="tag mono">{domain.apiName}</span>
              </div>
              <p className="muted">{domain.tagline || domain.description || '설명 없음'}</p>
              <div className="domain-card-foot">
                <span className="mono muted">{domain.apiBase}</span>
                <span className="domain-card-cta">콘솔 열기 →</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
