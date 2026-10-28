import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Route, Routes, useParams } from 'react-router-dom';

import { DomainConsole } from './domain-console/DomainConsole';
import { LandingPage } from './landing/LandingPage';
import './styles.css';

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/:domain/*" element={<DomainConsoleRoute />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);

/** Read the domain segment and hand it to the console. */
function DomainConsoleRoute() {
  const { domain = '' } = useParams();
  return <DomainConsole key={domain} domain={domain} />;
}
