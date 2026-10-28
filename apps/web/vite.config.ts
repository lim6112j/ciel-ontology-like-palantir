import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import react from '@vitejs/plugin-react';
import { defineConfig, type ProxyOptions } from 'vite';

interface DomainEntry {
  apiName: string;
  apiBase: string;
  backendUrl: string;
}

/**
 * `/api/<domain>/*` is proxied to that domain's backend instance, rewriting the
 * domain segment away so the backend keeps its plain `/api/...` paths. The list
 * comes from `generated/domains.json`, which `ontology export-web` writes.
 */
function domainProxies(): Record<string, ProxyOptions> {
  const manifestPath = resolve(__dirname, 'src/generated/domains.json');
  let domains: DomainEntry[] = [];
  try {
    domains = JSON.parse(readFileSync(manifestPath, 'utf8')) as DomainEntry[];
  } catch {
    // No generated bundle yet: the frontend will show its "run export-web" hint.
    return {};
  }
  return Object.fromEntries(
    domains.map((domain) => [
      `/api/${domain.apiName}`,
      {
        target: domain.backendUrl,
        changeOrigin: true,
        rewrite: (path: string) => path.replace(`/api/${domain.apiName}`, '/api'),
      },
    ]),
  );
}

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      ...domainProxies(),
      // Non-domain endpoints (health checks) still point at the default instance.
      '/health': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
});
