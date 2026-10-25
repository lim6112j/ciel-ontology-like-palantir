import { NavLink, Outlet } from 'react-router-dom';

const NAV = [
  { section: '에이전트' },
  { to: '/inbox', label: '제안 인박스' },
  { to: '/assistant', label: '운영 어시스턴트' },
  { section: '영업' },
  { to: '/outlets', label: '거래처' },
  { to: '/orders', label: '발주' },
  { to: '/orders/new', label: '발주 접수' },
  { section: '물류' },
  { to: '/deliveries', label: '배송 보드' },
  { section: '온톨로지' },
  { to: '/ontology', label: '스키마 브라우저' },
];

export function AppShell() {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          주류 도매 온톨로지
          <span>Ciel runtime</span>
        </div>
        <nav className="nav">
          {NAV.map((item, index) =>
            'section' in item ? (
              <div className="section" key={`s-${index}`}>
                {item.section}
              </div>
            ) : (
              <NavLink
                key={item.to}
                to={item.to!}
                className={({ isActive }) => (isActive ? 'active' : undefined)}
                end
              >
                {item.label}
              </NavLink>
            ),
          )}
        </nav>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
