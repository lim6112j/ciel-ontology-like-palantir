"""Generate the whole web bundle: one client per domain plus the landing manifest.

The frontend is a single build. `domains.json` / `domains.ts` tell it which
domains exist, and each domain's generated client is statically importable so
Vite bundles them all. Adding a domain is therefore a schema change plus a
regeneration, not a frontend edit.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ontology_runtime.config import list_domain_dirs
from ontology_runtime.meta.domain import DomainManifest
from ontology_runtime.registry import SchemaRegistry

_HEADER = """// GENERATED FILE — do not edit by hand.
// Regenerate with: uv run ontology export-web
"""


def _domain_entries(manifests: list[DomainManifest]) -> list[dict[str, Any]]:
    entries = [
        {
            "apiName": manifest.apiName,
            "displayName": manifest.displayName,
            "description": manifest.description,
            "tagline": manifest.web.tagline,
            "order": manifest.web.order,
            "apiBase": manifest.web_api_base,
            "backendUrl": manifest.web.backendUrl,
        }
        for manifest in manifests
        if manifest.web.enabled
    ]
    return sorted(entries, key=lambda entry: (entry["order"], entry["apiName"]))


def render_domains_json(entries: list[dict[str, Any]]) -> str:
    return json.dumps(entries, ensure_ascii=False, indent=2) + "\n"


def render_domains_ts(entries: list[dict[str, Any]]) -> str:
    """A typed wrapper plus a static `DOMAIN_APIS` map of every domain's client."""
    imports = "".join(
        f'import {{ api as {entry["apiName"]}Api }} from "./{entry["apiName"]}/client";\n'
        for entry in entries
    )
    body = json.dumps(entries, ensure_ascii=False, indent=2)
    api_map = "".join(f"  {entry['apiName']}: {entry['apiName']}Api,\n" for entry in entries)
    return (
        _HEADER
        + imports
        + "\nexport interface DomainEntry {\n"
        "  apiName: string;\n"
        "  displayName: string;\n"
        "  description?: string | null;\n"
        "  tagline: string;\n"
        "  order: number;\n"
        "  apiBase: string;\n"
        "  backendUrl: string;\n"
        "}\n\n"
        f"export const DOMAINS: DomainEntry[] = {body};\n\n"
        "export type DomainName = (typeof DOMAINS)[number]['apiName'];\n\n"
        "export const DOMAIN_APIS = {\n"
        f"  {api_map}".rstrip()
        + "\n} as const;\n"
        "\nexport const DOMAIN_BY_NAME: Record<string, DomainEntry> = Object.fromEntries(\n"
        "  DOMAINS.map((domain) => [domain.apiName, domain]),\n"
        ");\n"
    )


def write_web_bundle(out_dir: Path) -> list[Path]:
    """Generate every domain's client and the landing manifest under `out_dir`."""
    from ontology_runtime.clientgen.generator import write_client

    written: list[Path] = []
    manifests: list[DomainManifest] = []
    for directory in list_domain_dirs():
        registry = SchemaRegistry.from_domain(directory.name)
        manifest = registry.domain
        if manifest is None:
            continue
        manifests.append(manifest)
        written.extend(write_client(registry, out_dir / manifest.apiName))

    entries = _domain_entries(manifests)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "domains.json"
    json_path.write_text(render_domains_json(entries), encoding="utf-8")
    written.append(json_path)

    ts_path = out_dir / "domains.ts"
    ts_path.write_text(render_domains_ts(entries), encoding="utf-8")
    written.append(ts_path)
    return written
