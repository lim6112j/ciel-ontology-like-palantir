"""Generated TypeScript client and docs stay in sync with the schema."""

from __future__ import annotations

from pathlib import Path

import pytest

from ontology_runtime.clientgen.generator import (
    generate_actions,
    generate_client,
    generate_link_map,
    generate_types,
    render_ontology_markdown,
    write_client,
)
from ontology_runtime.registry import SchemaRegistry


@pytest.fixture(scope="module")
def registry() -> SchemaRegistry:
    return SchemaRegistry.from_domain("liquor")


def test_types_include_every_object_type(registry: SchemaRegistry) -> None:
    output = generate_types(registry)
    for name in registry.bundle.object_types:
        assert f"export interface {name} " in output
        assert f"export interface {name}Properties" in output
    assert "export const OBJECT_TYPE_NAMES" in output


def test_types_render_enums_as_unions(registry: SchemaRegistry) -> None:
    output = generate_types(registry)
    assert '"draft" | "submitted" | "confirmed"' in output


def test_actions_import_object_reference(registry: SchemaRegistry) -> None:
    output = generate_actions(registry)
    assert 'import type { ObjectReference } from "./client";' in output
    for name in registry.bundle.action_types:
        assert f"export interface {name}Params" in output


def test_links_import_object_type_name(registry: SchemaRegistry) -> None:
    output = generate_link_map(registry)
    assert 'import type { ObjectTypeName } from "./objects";' in output
    assert '"Delivery"' in output


def test_client_exposes_guardrailed_surface() -> None:
    registry = SchemaRegistry.from_domain("liquor")
    output = generate_client(registry)
    assert "validate:" in output and "apply:" in output
    assert "invokeAgent:" in output
    # The browser client must not offer a raw agent "apply".
    assert "agentApply" not in output


def test_write_client_creates_expected_files(registry: SchemaRegistry, tmp_path: Path) -> None:
    written = write_client(registry, tmp_path / "generated")
    names = {path.name for path in written}
    assert names == {"objects.ts", "actions.ts", "links.ts", "agents.ts", "client.ts", "index.ts"}
    assert all(path.stat().st_size > 0 for path in written)

    # Stable across runs: generation is deterministic except the dated VERSION.
    first = (tmp_path / "generated" / "objects.ts").read_text(encoding="utf-8")
    write_client(registry, tmp_path / "generated")
    assert (tmp_path / "generated" / "objects.ts").read_text(encoding="utf-8") == first


def test_markdown_docs_cover_all_sections(registry: SchemaRegistry) -> None:
    output = render_ontology_markdown(registry)
    assert "# 온톨로지 스키마" in output
    assert "## 오브젝트 타입" in output
    assert "## 액션 타입" in output
    assert "## 함수" in output
    assert "## 에이전트" in output
    assert "SalesOrder" in output


def test_agent_descriptions_are_json_escaped(registry: SchemaRegistry) -> None:
    from ontology_runtime.clientgen.generator import generate_agents

    output = generate_agents(registry)
    # Descriptions contain Korean and punctuation; they must be valid TS strings.
    assert 'description: "' in output
    assert "\\'" not in output
