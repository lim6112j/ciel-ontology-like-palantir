import { Navigate, Route, Routes } from 'react-router-dom';

import { AppShell } from '../components/AppShell';
import { AgentChat } from '../console/AgentChat';
import { ObjectExplorer } from '../console/ObjectExplorer';
import { ProposalInbox } from '../console/ProposalInbox';
import { SchemaBrowser } from '../console/SchemaBrowser';
import { loadDomainModule } from '../domains';

interface Props {
  domain: string;
}

/**
 * One domain's console. The generic screens come from `console/`; anything the
 * domain ships in `domains/<name>/index.ts` is appended as extra routes/nav.
 */
export function DomainConsole({ domain }: Props) {
  const module = loadDomainModule(domain);
  if (!module) {
    return <Navigate to="/" replace />;
  }

  const base = `/${domain}`;

  return (
    <Routes>
      <Route element={<AppShell domain={domain} extraNav={module.extraNav} />}>
        <Route index element={<Navigate to={`${base}/inbox`} replace />} />
        <Route
          path="inbox"
          element={
            <ProposalInbox
              api={module.api}
              domainName={domain}
              assistantPath={`${base}/assistant`}
            />
          }
        />
        <Route
          path="assistant"
          element={
            <AgentChat api={module.api} domainName={domain} presets={module.agentPresets} />
          }
        />
        <Route path="objects" element={<ObjectExplorer api={module.api} domainName={domain} />} />
        <Route path="schema" element={<SchemaBrowser api={module.api} domainName={domain} />} />
        {module.extraRoutes.map((route) => (
          <Route key={route.path} path={route.path} element={<route.element />} />
        ))}
        <Route path="*" element={<Navigate to={`${base}/inbox`} replace />} />
      </Route>
    </Routes>
  );
}
