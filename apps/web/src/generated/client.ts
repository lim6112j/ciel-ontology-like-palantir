// GENERATED FILE — do not edit by hand.
// Regenerate with: uv run ontology export-client --out apps/web/src/generated

export interface ObjectReference {
  objectType: string;
  rid: string;
}

export interface SearchBody {
  filter?: unknown;
  orderBy?: Record<string, 'asc' | 'desc'> | { field: string; direction: 'asc' | 'desc' }[];
  pageSize?: number;
  pageToken?: number;
}

export interface Envelope<T> {
  success: boolean;
  data: T;
  error: { code: string; message: string; details?: Record<string, unknown> } | null;
  meta: Record<string, unknown>;
}

export interface PageMeta {
  total: number;
  pageSize: number;
  pageToken: number;
  nextPageToken: number | null;
}

export interface Violation {
  code: string;
  path: string;
  message: string;
  objectType?: string;
  objectRef?: string;
  severity: string;
}

const BASE = import.meta.env?.VITE_API_BASE ?? '/api';

async function request<T>(
  path: string,
  init: RequestInit = {},
  actor = 'web',
): Promise<Envelope<T>> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'content-type': 'application/json',
      'X-Actor': actor,
      ...(init.headers ?? {}),
    },
  });
  const body = (await response.json()) as Envelope<T>;
  return body;
}

export const api = {
  health: () => request<{ status: string; objectTypes: number }>('/../health'),

  objectTypes: () => request<unknown[]>('/ontology/objectTypes'),
  objectType: (apiName: string) => request<unknown>(`/ontology/objectTypes/${apiName}`),
  actionTypes: () => request<unknown[]>('/ontology/actionTypes'),
  actionType: (apiName: string) => request<unknown>(`/ontology/actionTypes/${apiName}`),
  agents: () => request<unknown[]>('/ontology/agents'),

  search: <T>(objectType: string, body: SearchBody = {}) =>
    request<T[]>(`/objectsets/${objectType}/search`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  aggregate: <T>(objectType: string, body: unknown) =>
    request<T[]>(`/objectsets/${objectType}/aggregate`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  get: <T>(objectType: string, rid: string) => request<T>(`/objects/${objectType}/${rid}`),
  linked: <T>(objectType: string, rid: string, linkName: string) =>
    request<T[]>(`/objects/${objectType}/${rid}/links/${linkName}`),
  create: <T>(objectType: string, properties: unknown) =>
    request<T>(`/objects/${objectType}`, { method: 'POST', body: JSON.stringify({ properties }) }),
  update: <T>(objectType: string, rid: string, properties: unknown) =>
    request<T>(`/objects/${objectType}/${rid}`, {
      method: 'PATCH',
      body: JSON.stringify({ properties }),
    }),

  validate: (action: string, params: unknown) =>
    request<{ status: string; violations: Violation[]; data: Record<string, unknown> }>(
      `/actions/${action}/validate`,
      { method: 'POST', body: JSON.stringify({ params }) },
    ),
  apply: (action: string, params: unknown, idempotencyKey?: string) =>
    request<{ status: string; data: Record<string, unknown>; violated?: Violation[] }>(
      `/actions/${action}/apply`,
      {
        method: 'POST',
        body: JSON.stringify({ params }),
        headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {},
      },
    ),

  runFunction: <T>(name: string, params: unknown) =>
    request<T>(`/functions/${name}/execute`, { method: 'POST', body: JSON.stringify({ params }) }),

  invokeAgent: (agent: string, input: string) =>
    request<{
      agent: string;
      status: string;
      runNo: string;
      finalMessage: string;
      proposals: string[];
      toolCalls: { tool: string; isError?: boolean; result?: string }[];
    }>(`/agents/${agent}/invoke`, { method: 'POST', body: JSON.stringify({ input }) }),
  proposals: (status?: string) =>
    request<unknown[]>(`/proposals${status ? `?status=${status}` : ''}`),
  agentRuns: () => request<unknown[]>('/agentRuns'),
};

export const VERSION = 'generated-20261025';
