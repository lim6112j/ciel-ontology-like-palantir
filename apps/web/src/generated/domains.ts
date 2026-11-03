// GENERATED FILE — do not edit by hand.
// Regenerate with: uv run ontology export-web
import { api as liquorApi } from "./liquor/client";
import { api as bakeryApi } from "./bakery/client";
import { api as makgeolliApi } from "./makgeolli/client";
import { DIAGRAM_MERMAID as liquorDiagram, DIAGRAM_COUNTS as liquorDiagramCounts } from "./liquor/diagram";
import { DIAGRAM_MERMAID as bakeryDiagram, DIAGRAM_COUNTS as bakeryDiagramCounts } from "./bakery/diagram";
import { DIAGRAM_MERMAID as makgeolliDiagram, DIAGRAM_COUNTS as makgeolliDiagramCounts } from "./makgeolli/diagram";

export interface DomainEntry {
  apiName: string;
  displayName: string;
  description?: string | null;
  tagline: string;
  order: number;
  apiBase: string;
  backendUrl: string;
}

export const DOMAINS: DomainEntry[] = [
  {
    "apiName": "liquor",
    "displayName": "주류 도매",
    "description": "한국 주류 도매 사업자의 영업·발주·배차·납품 온톨로지.",
    "tagline": "주류 도매 영업·배차·납품 운영 콘솔",
    "order": 10,
    "apiBase": "/api/liquor",
    "backendUrl": "http://localhost:8000"
  },
  {
    "apiName": "bakery",
    "displayName": "베이커리 유통",
    "description": "베이커리 생산·매장·배치 재고 온톨로지. 주류 도메인과 완전히 독립적이다.",
    "tagline": "베이커리 생산·매장·배치 재고 콘솔",
    "order": 20,
    "apiBase": "/api/bakery",
    "backendUrl": "http://localhost:8001"
  },
  {
    "apiName": "makgeolli",
    "displayName": "양조장(막걸리)",
    "description": "막걸리 양조장의 양조(발효·숙성·온도관리)·판매·유통·재고 온톨로지.",
    "tagline": "막걸리 양조·온도·판매·유통 운영 콘솔",
    "order": 30,
    "apiBase": "/api/makgeolli",
    "backendUrl": "http://localhost:8002"
  }
];

export type DomainName = (typeof DOMAINS)[number]['apiName'];

export const DOMAIN_APIS = {
    liquor: liquorApi,
  bakery: bakeryApi,
  makgeolli: makgeolliApi,
} as const;

export interface DiagramCounts {
  objectTypes: number;
  linkTypes: number;
  actionTypes: number;
  agentProposableActions: number;
}

/** Mermaid erDiagram source per domain, generated from that domain's YAML. */
export const DOMAIN_DIAGRAMS: Record<string, string> = {
    liquor: liquorDiagram,
  bakery: bakeryDiagram,
  makgeolli: makgeolliDiagram,
};

export const DOMAIN_DIAGRAM_COUNTS: Record<string, DiagramCounts> = {
    liquor: liquorDiagramCounts,
  bakery: bakeryDiagramCounts,
  makgeolli: makgeolliDiagramCounts,
};

export const DOMAIN_BY_NAME: Record<string, DomainEntry> = Object.fromEntries(
  DOMAINS.map((domain) => [domain.apiName, domain]),
);
