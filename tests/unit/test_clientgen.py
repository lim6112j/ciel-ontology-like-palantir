"""Generated TypeScript client and docs stay in sync with the schema."""

from __future__ import annotations

from pathlib import Path

import pytest

from ontology_runtime.clientgen.generator import (
    _action_touchpoints,
    generate_actions,
    generate_client,
    generate_diagram,
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


def test_diagram_is_an_er_diagram(registry: SchemaRegistry) -> None:
    output = generate_diagram(registry)
    assert output.startswith("erDiagram")
    # Every object type becomes an entity, and every link type exactly one edge.
    for name in registry.bundle.object_types:
        assert f"\n    {name} {{" in output
    for link in registry.bundle.link_types.values():
        assert f'"{link.source_link_name()}"' in output


def test_diagram_edges_carry_cardinality_and_link_name(registry: SchemaRegistry) -> None:
    output = generate_diagram(registry)
    # deliveryStops: one delivery has many stops, a stop belongs to one delivery.
    assert 'Delivery ||--o{ DeliveryStop : "stops"' in output
    # One edge per link type, not one per derived direction.
    assert output.count("Delivery ||--o{ DeliveryStop") == 1
    # The inverse direction is not emitted as a second edge.
    assert 'DeliveryStop ||--o{ Delivery : "delivery"' not in output


def test_diagram_marks_primary_and_unique_keys(registry: SchemaRegistry) -> None:
    output = generate_diagram(registry)
    order_block = output.split("\n    SalesOrder {", 1)[1].split("\n    }", 1)[0]
    assert "string orderNo PK" in order_block
    assert "objectRef outletRid FK" in order_block


def test_diagram_connects_actions_to_the_objects_they_touch(registry: SchemaRegistry) -> None:
    output = generate_diagram(registry)
    # Function-backed actions are wired through the function's own parameters.
    assert 'PlanDeliveries ||..o{ Depot : "uses"' in output
    # Declarative actions show their create/modify targets.
    assert 'ConfirmSalesOrder ||..o{ SalesOrder : "modifies"' in output
    # Actions are not entities with properties.
    assert "\n    ConfirmSalesOrder {" not in output


def test_diagram_colors_actions_differently_from_objects(registry: SchemaRegistry) -> None:
    output = generate_diagram(registry)
    # Objects wear the console's slate tones, actions the amber accent.
    assert "style SalesOrder fill:#1b2029,stroke:#3a4252,color:#e6e9ef" in output
    assert "style ConfirmSalesOrder fill:#3a2f16,stroke:#e0a63c,color:#f2cf8a" in output
    # Only actions that touch an object are drawn, so only they get a style line.
    for action in registry.bundle.action_types.values():
        touchpoints = _action_touchpoints(registry, action)
        styled = f"style {action.apiName} fill:" in output
        assert styled == bool(touchpoints), action.apiName


def test_diagram_labels_are_quote_safe(registry: SchemaRegistry) -> None:
    output = generate_diagram(registry)
    for line in output.splitlines():
        if "--" in line and ":" in line:
            label = line.rsplit(":", 1)[1].strip()
            assert label.startswith('"') and label.endswith('"'), line
            # Mermaid labels are single-quoted strings here: no nested quotes/backslashes.
            assert "\\" not in label


def test_write_client_creates_expected_files(registry: SchemaRegistry, tmp_path: Path) -> None:
    written = write_client(registry, tmp_path / "generated")
    names = {path.name for path in written}
    assert names == {
        "objects.ts",
        "actions.ts",
        "links.ts",
        "agents.ts",
        "client.ts",
        "index.ts",
        "diagram.ts",
    }
    diagram = (tmp_path / "generated" / "diagram.ts").read_text(encoding="utf-8")
    assert "export const DIAGRAM_MERMAID" in diagram
    assert "export const DIAGRAM_COUNTS" in diagram
    assert diagram.startswith("// GENERATED FILE")
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
