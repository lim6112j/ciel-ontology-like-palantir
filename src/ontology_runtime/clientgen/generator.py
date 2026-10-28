"""Generate a typed TypeScript client from the ontology registry.

This is the local analogue of Foundry's OSDK generation: the UI never guesses
a property name or action parameter, it consumes generated types.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from ontology_runtime.meta.property import PropertyType
from ontology_runtime.registry import SchemaRegistry

TS_TYPE: dict[PropertyType, str] = {
    PropertyType.STRING: "string",
    PropertyType.TEXT: "string",
    PropertyType.INTEGER: "number",
    PropertyType.BIGINT: "number",
    PropertyType.DECIMAL: "number",
    PropertyType.BOOLEAN: "boolean",
    PropertyType.DATE: "string",
    PropertyType.TIMESTAMP: "string",
    PropertyType.ENUM: "string",
    PropertyType.OBJECT_REF: "string",
    PropertyType.JSON: "unknown",
}

HEADER = """// GENERATED FILE — do not edit by hand.
// Regenerate with: uv run ontology export-web
"""


def _doc(text: str | None) -> str:
    return f"/** {text} */\n" if text else ""


def generate_types(registry: SchemaRegistry) -> str:
    lines = [HEADER, ""]
    for obj in registry.bundle.object_types.values():
        lines.append(_doc(obj.description))
        lines.append(f"export interface {obj.apiName}Properties {{\n")
        for prop in obj.properties.values():
            optional = "" if prop.required else "?"
            enum = (
                " | ".join(f'"{value}"' for value in prop.values)
                if prop.type is PropertyType.ENUM and prop.values
                else TS_TYPE[prop.type]
            )
            lines.append(f"  /** {prop.displayName or prop.apiName} */\n")
            lines.append(f"  {prop.apiName}{optional}: {enum};\n")
        lines.append("}\n\n")
        lines.append(f"export interface {obj.apiName} {{\n")
        lines.append("  rid: string;\n  objectType: string;\n")
        lines.append(f"  properties: {obj.apiName}Properties;\n")
        lines.append(
            "  version?: number;\n  createdAt?: string | null;\n  updatedAt?: string | null;\n"
        )
        lines.append("}\n\n")

    lines.append("export const OBJECT_TYPE_NAMES = [\n")
    for name in registry.bundle.object_types:
        lines.append(f'  "{name}",\n')
    lines.append("] as const;\n")
    lines.append("export type ObjectTypeName = (typeof OBJECT_TYPE_NAMES)[number];\n\n")

    lines.append("export type ObjectPropertiesByName = {\n")
    for name in registry.bundle.object_types:
        lines.append(f"  {name}: {name}Properties;\n")
    lines.append("};\n\n")

    lines.append("export type ObjectByName = {\n")
    for name in registry.bundle.object_types:
        lines.append(f"  {name}: {name};\n")
    lines.append("};\n")
    return "".join(lines)


def generate_actions(registry: SchemaRegistry) -> str:
    lines = [HEADER, 'import type { ObjectReference } from "./client";', ""]
    for action in registry.bundle.action_types.values():
        lines.append(_doc(action.description))
        lines.append(f"export interface {action.apiName}Params {{\n")
        for param in action.parameters.values():
            optional = "" if param.required else "?"
            if param.type.value in {"objectRef"}:
                ts_type = "ObjectReference"
            elif param.type.value == "objectSet":
                ts_type = "ObjectReference[]"
            elif param.type.value == "enum" and param.values:
                ts_type = " | ".join(f'"{value}"' for value in param.values)
            elif param.type.value in {"date", "timestamp"}:
                ts_type = "string"
            elif param.type.value in {"integer", "decimal"}:
                ts_type = "number"
            elif param.type.value == "boolean":
                ts_type = "boolean"
            elif param.type.value == "json":
                ts_type = "unknown"
            else:
                ts_type = "string"
            lines.append(f"  /** {param.displayName or param.apiName} */\n")
            lines.append(f"  {param.apiName}{optional}: {ts_type};\n")
        lines.append("}\n\n")

    lines.append("export const ACTION_NAMES = [\n")
    for name in registry.bundle.action_types:
        lines.append(f'  "{name}",\n')
    lines.append("] as const;\n")
    lines.append("export type ActionName = (typeof ACTION_NAMES)[number];\n\n")
    lines.append("export interface ActionParamsByName {\n")
    for name in registry.bundle.action_types:
        lines.append(f"  {name}: {name}Params;\n")
    lines.append("}\n")
    return "".join(lines)


def generate_link_map(registry: SchemaRegistry) -> str:
    lines = [
        HEADER,
        'import type { ObjectTypeName } from "./objects";',
        "",
        "export const LINKS: Record<\n"
        "  string,\n"
        "  { target: ObjectTypeName; cardinality: 'one' | 'many' }[]\n"
        "> = {\n",
    ]
    for obj in registry.bundle.object_types.values():
        views = registry.links_of(obj.apiName)
        if not views:
            lines.append(f"  {obj.apiName}: [],\n")
            continue
        lines.append(f"  {obj.apiName}: [\n")
        for view in views:
            lines.append(
                f'    {{ target: "{view.target_type}", cardinality: "{view.cardinality.value}" }}, '
                f"// {view.link_name}\n"
            )
        lines.append("  ],\n")
    lines.append("};\n")
    return "".join(lines)


def generate_agents(registry: SchemaRegistry) -> str:
    lines = [HEADER, ""]
    for agent in registry.bundle.agents.values():
        description = json.dumps(agent.description or "", ensure_ascii=False)
        lines.append(
            f"export const {agent.apiName} = {{\n"
            f'  apiName: "{agent.apiName}",\n'
            f'  displayName: "{agent.displayName}",\n'
            f'  kind: "{agent.kind.value}",\n'
            f"  description: {description},\n"
            f"}} as const;\n\n"
        )
    lines.append("export const AGENTS = [\n")
    for agent in registry.bundle.agents.values():
        lines.append(f"  {agent.apiName},\n")
    lines.append("] as const;\n")
    return "".join(lines)


def generate_client(registry: SchemaRegistry) -> str:
    api_base = registry.domain.web_api_base if registry.domain else "/api"
    env_key = f"VITE_API_BASE_{registry.domain_name.upper()}"
    return HEADER + (
        """
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

const BASE = import.meta.env?.{envKey} ?? '{apiBase}';

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
  health: () => request<{ status: string; domain: string; objectTypes: number }>('/health'),

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

export const VERSION = 'generated-{timestamp}';
""".replace("{timestamp}", dt.datetime.now(dt.UTC).strftime("%Y%m%d"))
    ).replace("{apiBase}", api_base).replace("{envKey}", env_key)


def write_client(registry: SchemaRegistry, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "objects.ts": generate_types(registry),
        "actions.ts": generate_actions(registry),
        "links.ts": generate_link_map(registry),
        "agents.ts": generate_agents(registry),
        "client.ts": generate_client(registry),
        "index.ts": HEADER
        + '\nexport * from "./objects";\nexport * from "./actions";\nexport * from "./links";\n'
        'export * from "./agents";\nexport * from "./client";\n',
    }
    written = []
    for name, content in files.items():
        path = out_dir / name
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


def render_ontology_markdown(registry: SchemaRegistry) -> str:
    """Human docs generated from the same source of truth as the runtime."""
    lines = ["# 온톨로지 스키마", "", f"생성일: {dt.date.today().isoformat()}", ""]
    lines.append("## 오브젝트 타입")
    for obj in registry.bundle.object_types.values():
        lines.append(f"\n### {obj.apiName} — {obj.displayName}")
        if obj.description:
            lines.append(f"\n{obj.description}")
        lines.append(f"\n- 기본키: `{obj.primaryKey}`")
        if obj.stateMachine:
            transitions = ", ".join(f"{t.from_}→{t.to}" for t in obj.stateMachine.transitions)
            lines.append(f"- 상태머신: {transitions}")
        lines.append("\n| 속성 | 타입 | 필수 | 인덱스 |")
        lines.append("|---|---|---|---|")
        for prop in obj.properties.values():
            lines.append(
                f"| {prop.apiName} ({prop.displayName or ''}) | {prop.type.value} | "
                f"{'O' if prop.required else ''} | {'O' if prop.indexed else ''} |"
            )
        lines.append(
            "\n링크: "
            + ", ".join(
                f"`{v.link_name}` → {v.target_type}" for v in registry.links_of(obj.apiName)
            )
        )
    lines.append("\n## 액션 타입\n")
    for action in registry.bundle.action_types.values():
        kind = "함수 기반" if action.is_function_backed() else "선언형"
        lines.append(
            f"- **{action.apiName}** ({action.displayName}, {kind}) — {action.description or ''}"
        )
    lines.append("\n## 함수\n")
    for fn in registry.bundle.functions.values():
        lines.append(f"- **{fn.apiName}** ({fn.kind.value}) — {fn.description or ''}")
    lines.append("\n## 에이전트\n")
    for agent in registry.bundle.agents.values():
        lines.append(
            f"- **{agent.apiName}** ({agent.displayName}) — 제안 가능: "
            f"{', '.join(agent.allowedActionTypes) or '없음'}"
        )
    return "\n".join(lines) + "\n"
