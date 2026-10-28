/**
 * The subset of the generated client the shared console uses.
 *
 * Every domain's `generated/<domain>/client.ts` exposes the same call surface,
 * only with different type parameters, so the console can be written once and
 * handed whichever domain's `api` object is active.
 */

export interface Envelope<T> {
  success: boolean;
  data: T;
  error: { code: string; message: string; details?: Record<string, unknown> } | null;
  meta: Record<string, unknown>;
}

export interface Violation {
  code: string;
  path: string;
  message: string;
  objectType?: string;
  objectRef?: string;
  severity: string;
}

export interface ObjectReference {
  objectType: string;
  rid: string;
}

export interface SearchBody {
  filter?: unknown;
  orderBy?: unknown;
  pageSize?: number;
  pageToken?: number;
  select?: string[];
}

export interface PageMeta {
  total: number;
  pageSize: number;
  pageToken: number;
  nextPageToken: number | null;
}

export interface DomainApi {
  health: () => Promise<Envelope<{ status: string; domain: string; objectTypes: number }>>;
  objectTypes: () => Promise<Envelope<unknown[]>>;
  objectType: (apiName: string) => Promise<Envelope<unknown>>;
  actionTypes: () => Promise<Envelope<unknown[]>>;
  actionType: (apiName: string) => Promise<Envelope<unknown>>;
  agents: () => Promise<Envelope<unknown[]>>;
  search: <T>(objectType: string, body?: SearchBody) => Promise<Envelope<T[]>>;
  aggregate: <T>(objectType: string, body: unknown) => Promise<Envelope<T[]>>;
  get: <T>(objectType: string, rid: string) => Promise<Envelope<T>>;
  linked: <T>(objectType: string, rid: string, linkName: string) => Promise<Envelope<T[]>>;
  create: <T>(objectType: string, properties: unknown) => Promise<Envelope<T>>;
  update: <T>(objectType: string, rid: string, properties: unknown) => Promise<Envelope<T>>;
  validate: (
    action: string,
    params: unknown,
  ) => Promise<Envelope<{ status: string; violations: Violation[]; data: Record<string, unknown> }>>;
  apply: (
    action: string,
    params: unknown,
    idempotencyKey?: string,
  ) => Promise<Envelope<{ status: string; data: Record<string, unknown>; violated?: Violation[] }>>;
  runFunction: <T>(name: string, params: unknown) => Promise<Envelope<T>>;
  invokeAgent: (agent: string, input: string) => Promise<
    Envelope<{
      agent: string;
      status: string;
      runNo: string;
      finalMessage: string;
      proposals: string[];
      toolCalls: { tool: string; isError?: boolean; result?: string }[];
    }>
  >;
  proposals: (status?: string) => Promise<Envelope<unknown[]>>;
  agentRuns: () => Promise<Envelope<unknown[]>>;
}

export interface ObjectTypeSummary {
  apiName: string;
  displayName: string;
  description?: string | null;
  primaryKey: string;
  internal: boolean;
  propertyCount: number;
  links: { apiName: string; targetType: string; cardinality: string }[];
}

export interface ObjectTypeDetail extends Omit<ObjectTypeSummary, 'links' | 'propertyCount'> {
  properties: Record<
    string,
    {
      apiName: string;
      displayName?: string | null;
      type: string;
      required: boolean;
      indexed: boolean;
      unique: boolean;
      values: string[] | null;
      objectType?: string | null;
      description?: string | null;
    }
  >;
  links: { apiName: string; targetType: string; cardinality: string; linkType: string }[];
}

export interface ActionTypeSummary {
  apiName: string;
  displayName: string;
  description?: string | null;
  agentProposable: boolean;
  functionBacked: boolean;
}

export interface AgentSummary {
  apiName: string;
  displayName: string;
  description?: string | null;
  kind: string;
  allowedActionTypes: string[];
  allowedFunctions: string[];
}

export interface OntologyObject {
  rid: string;
  objectType: string;
  properties: Record<string, unknown>;
  version?: number;
}
