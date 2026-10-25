"""Loader tests: YAML parsing, duplicate detection, and referential integrity."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ontology_runtime.errors import SchemaError
from ontology_runtime.loader import load_schema

PROP = {"apiName": "name", "type": "string", "required": True}


def _write(root: Path, relative: str, payload: object) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")


def _object(name: str, **extra) -> dict:
    data = {
        "apiName": name,
        "displayName": name,
        "primaryKey": "name",
        "properties": {"name": dict(PROP)},
    }
    data.update(extra)
    return data


@pytest.fixture
def schema_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "schema"
    (directory / "object_types").mkdir(parents=True)
    (directory / "action_types").mkdir(parents=True)
    (directory / "agents").mkdir(parents=True)
    return directory


def test_loads_minimal_schema(schema_dir: Path) -> None:
    _write(schema_dir, "object_types/Outlet.yaml", _object("Outlet"))
    bundle = load_schema(schema_dir)
    assert set(bundle.object_types) == {"Outlet"}
    assert bundle.object_types["Outlet"].primaryKey == "name"


def test_duplicate_object_type_rejected(schema_dir: Path) -> None:
    _write(schema_dir, "object_types/A.yaml", _object("Outlet"))
    _write(schema_dir, "object_types/B.yaml", _object("Outlet"))
    with pytest.raises(SchemaError, match="duplicate object type apiName 'Outlet'"):
        load_schema(schema_dir)


def test_link_requires_declared_object_types(schema_dir: Path) -> None:
    _write(schema_dir, "object_types/Outlet.yaml", _object("Outlet"))
    _write(
        schema_dir,
        "link_types.yaml",
        {
            "linkTypes": [
                {
                    "apiName": "orders",
                    "displayName": "orders",
                    "fromObjectType": "Outlet",
                    "toObjectType": "Ghost",
                }
            ]
        },
    )
    with pytest.raises(SchemaError, match="to object type 'Ghost' is not declared"):
        load_schema(schema_dir)


def test_link_name_collision_rejected(schema_dir: Path) -> None:
    _write(schema_dir, "object_types/Outlet.yaml", _object("Outlet"))
    _write(schema_dir, "object_types/Order.yaml", _object("Order"))
    _write(schema_dir, "object_types/Rep.yaml", _object("Rep"))
    _write(
        schema_dir,
        "link_types.yaml",
        {
            "linkTypes": [
                {
                    "apiName": "orders",
                    "displayName": "orders",
                    "fromObjectType": "Outlet",
                    "toObjectType": "Order",
                },
                {
                    "apiName": "orders2",
                    "displayName": "orders2",
                    "fromObjectType": "Outlet",
                    "fromApiName": "orders",
                    "toObjectType": "Rep",
                },
            ]
        },
    )
    with pytest.raises(SchemaError, match="collides with link type"):
        load_schema(schema_dir)


def test_action_with_unknown_function_rejected(schema_dir: Path) -> None:
    _write(schema_dir, "object_types/Outlet.yaml", _object("Outlet"))
    _write(
        schema_dir,
        "action_types/Bad.yaml",
        {
            "apiName": "Bad",
            "displayName": "Bad",
            "rules": [{"type": "runFunction", "function": "missing"}],
        },
    )
    with pytest.raises(SchemaError, match="unknown function 'missing'"):
        load_schema(schema_dir)


def test_action_rule_property_checked_against_object_type(schema_dir: Path) -> None:
    _write(schema_dir, "object_types/Outlet.yaml", _object("Outlet"))
    _write(
        schema_dir,
        "action_types/Bad.yaml",
        {
            "apiName": "Bad",
            "displayName": "Bad",
            "rules": [{"type": "createObject", "objectType": "Outlet", "properties": {"ghost": 1}}],
        },
    )
    with pytest.raises(SchemaError, match="unknown properties \\['ghost'\\]"):
        load_schema(schema_dir)


def test_agent_may_only_reference_proposable_actions(schema_dir: Path) -> None:
    _write(schema_dir, "object_types/Outlet.yaml", _object("Outlet"))
    _write(
        schema_dir,
        "action_types/Hidden.yaml",
        {
            "apiName": "Hidden",
            "displayName": "Hidden",
            "agentProposable": False,
            "rules": [{"type": "deleteObject", "target": {"objectType": "Outlet"}}],
        },
    )
    _write(
        schema_dir,
        "agents/a.yaml",
        {
            "apiName": "a",
            "displayName": "a",
            "kind": "intake",
            "systemPrompt": "hi",
            "allowedActionTypes": ["Hidden"],
        },
    )
    with pytest.raises(SchemaError, match="is not agent-proposable"):
        load_schema(schema_dir)


def test_agent_may_not_call_write_functions(schema_dir: Path) -> None:
    _write(schema_dir, "object_types/Outlet.yaml", _object("Outlet"))
    _write(
        schema_dir,
        "functions.yaml",
        {
            "functions": [
                {
                    "apiName": "doWrite",
                    "displayName": "doWrite",
                    "kind": "write",
                    "implementation": "x.y",
                }
            ]
        },
    )
    _write(
        schema_dir,
        "agents/a.yaml",
        {
            "apiName": "a",
            "displayName": "a",
            "kind": "intake",
            "systemPrompt": "hi",
            "allowedFunctions": ["doWrite"],
        },
    )
    with pytest.raises(SchemaError, match="is a write function"):
        load_schema(schema_dir)


def test_agent_prompt_file_is_inlined(schema_dir: Path) -> None:
    _write(schema_dir, "object_types/Outlet.yaml", _object("Outlet"))
    (schema_dir / "prompts").mkdir()
    (schema_dir / "prompts" / "intake.md").write_text("주문을 접수하세요.", encoding="utf-8")
    _write(
        schema_dir,
        "agents/a.yaml",
        {
            "apiName": "a",
            "displayName": "a",
            "kind": "intake",
            "systemPromptFile": "prompts/intake.md",
        },
    )
    bundle = load_schema(schema_dir)
    assert bundle.agents["a"].systemPrompt == "주문을 접수하세요."


def test_schema_hash_is_stable(schema_dir: Path) -> None:
    _write(schema_dir, "object_types/Outlet.yaml", _object("Outlet"))
    first = load_schema(schema_dir).schema_hash()
    second = load_schema(schema_dir).schema_hash()
    assert first == second
