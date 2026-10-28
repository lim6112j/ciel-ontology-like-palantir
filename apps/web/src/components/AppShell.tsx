import { NavLink, Outlet } from 'react-router-dom';

import { DOMAIN_BY_NAME } from '../generated/domains';
import type { NavItem } from '../domains';

interface Props {
  domain: string;
  extraNav: NavItem[];
}

/** Generic console sections every domain gets, plus whatever the domain adds. */
const BASE_NAV: { section: string; items: NavItem[] }[] = [
  {
    section: '에이전트',
    items: [
      { to: 'inbox', label: '제안 인박스' },
      { to: 'assistant', label: '운영 어시스턴트' },
    ],
  },
  {
    section: '온톨로지',
    items: [
      { to: 'objects', label: '객체 탐색기' },
      { to: 'schema', label: '스키마 브라우저' },
    ],
  },
];

export function AppShell({ domain, extraNav }: Props) {
  const entry = DOMAIN_BY_NAME[domain];
  const sections = extraNav.length > 0
    ? [
        ...BASE_NAV.slice(0, 1),
        { section: entry?.displayName ?? domain, items: extraNav },
        ...BASE_NAV.slice(1),
      ]
    : BASE_NAV;

  return (
    <div className="shell">
      <aside className="sidebar">
        <NavLink to="/" className="brand" style={{ textDecoration: 'none', color: 'inherit' }}>
          {entry?.displayName ?? domain}
          <span>← 도메인 목록</span>
        </NavLink>
        <nav className="nav">
          {sections.map((section) => (
            <div key={section.section}>
              <div className="section">{section.section}</div>
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={`/${domain}/${item.to}`}
                  className={({ isActive }) => (isActive ? 'active' : undefined)}
                  end
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
