/**
 * Per-domain console customization.
 *
 * A domain works with the generic console out of the box; this file only adds
 * the extra navigation, routes, and agent presets a domain chooses to ship.
 * The generated `DOMAIN_APIS` map already provides the base client, so a
 * domain with no entry here still gets a working console.
 */

import type { ComponentType } from 'react';

import { DOMAIN_APIS } from '../generated/domains';
import type { AgentPreset } from '../console/AgentChat';
import type { DomainApi } from '../console/api';

export interface NavItem {
  to: string;
  label: string;
}

export interface ExtraRoute {
  path: string;
  element: ComponentType;
}

export interface DomainModule {
  api: DomainApi;
  extraNav: NavItem[];
  extraRoutes: ExtraRoute[];
  agentPresets: AgentPreset[];
}

export interface DomainOverrides {
  extraNav?: NavItem[];
  extraRoutes?: ExtraRoute[];
  agentPresets?: AgentPreset[];
}

/** Vite statically analyses this glob, so only existing folders are bundled. */
const overrides = import.meta.glob<DomainOverrides>('./*/index.ts', {
  eager: true,
  import: 'default',
});

export function loadDomainModule(name: string): DomainModule | null {
  const api = (DOMAIN_APIS as Record<string, DomainApi | undefined>)[name];
  if (!api) return null;

  const custom = overrides[`./${name}/index.ts`] ?? {};
  return {
    api,
    extraNav: custom.extraNav ?? [],
    extraRoutes: custom.extraRoutes ?? [],
    agentPresets: custom.agentPresets ?? [],
  };
}
