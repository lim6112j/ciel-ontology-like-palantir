import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import { AppShell } from './components/AppShell';
import { AgentInbox } from './pages/AgentInbox';
import { AgentChat } from './pages/AgentChat';
import { DeliveryBoard } from './pages/DeliveryBoard';
import { OntologyBrowser } from './pages/OntologyBrowser';
import { OrderComposer } from './pages/OrderComposer';
import { Orders } from './pages/Orders';
import { OutletDetail } from './pages/OutletDetail';
import { Outlets } from './pages/Outlets';
import './styles.css';

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Navigate to="/inbox" replace />} />
            <Route path="/inbox" element={<AgentInbox />} />
            <Route path="/assistant" element={<AgentChat />} />
            <Route path="/outlets" element={<Outlets />} />
            <Route path="/outlets/:rid" element={<OutletDetail />} />
            <Route path="/orders" element={<Orders />} />
            <Route path="/orders/new" element={<OrderComposer />} />
            <Route path="/deliveries" element={<DeliveryBoard />} />
            <Route path="/ontology" element={<OntologyBrowser />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
