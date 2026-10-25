"""Load the YAML ontology schema and validate cross-references."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ontology_runtime.errors import SchemaError
from ontology_runtime.meta import (
    ActionTypeDef,
    AgentDef,
    FunctionDef,
    FunctionKind,
    LinkTypeDef,
    ObjectTypeDef,
    ParameterType,
)


class SchemaBundle:
    """The loaded, cross-validated ontology schema."""

    def __init__(
        self,
        object_types: dict[str, ObjectTypeDef],
        link_types: dict[str, LinkTypeDef],
        action_types: dict[str, ActionTypeDef],
        functions: dict[str, FunctionDef],
        agents: dict[str, AgentDef],
        interfaces: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.object_types = object_types
        self.link_types = link_types
        self.action_types = action_types
        self.functions = functions
        self.agents = agents
        #: Reserved: interface names only. No runtime semantics in v1.
        self.interfaces = interfaces or {}

    def schema_hash(self) -> str:
        payload = {
            "objectTypes": {
                k: v.model_dump(mode="json") for k, v in sorted(self.object_types.items())
            },
            "linkTypes": {k: v.model_dump(mode="json") for k, v in sorted(self.link_types.items())},
        }
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
        return hashlib.sha256(blob).hexdigest()


def _read_yaml(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise SchemaError(f"{path.name}: invalid YAML: {exc}") from exc


def _profile(spec: type, data: dict[str, Any], source: str) -> Any:
    try:
        return spec(**data)
    except ValidationError as exc:
        raise SchemaError(f"{source}: {exc}") from exc


def _iter_files(directory: Path, pattern: str) -> Iterable[Path]:
    return sorted(directory.glob(pattern)) if directory.is_dir() else []


def load_schema(schema_dir: Path) -> SchemaBundle:
    """Parse schema files and enforce referential integrity.

    Raises SchemaError with a readable message on the first problem found.
    """
    object_types = _load_object_types(schema_dir)
    functions = _load_collection(
        schema_dir / "functions.yaml", "functions", FunctionDef, "function"
    )
    link_types = _load_collection(
        schema_dir / "link_types.yaml", "linkTypes", LinkTypeDef, "link type"
    )
    action_types = _load_object_types(
        schema_dir, subdir="action_types", spec=ActionTypeDef, kind="action type"
    )
    agents = _load_agents(schema_dir)
    interfaces = _load_interfaces(schema_dir)

    bundle = SchemaBundle(object_types, link_types, action_types, functions, agents, interfaces)
    _validate_references(bundle)
    return bundle


def _load_object_types(
    schema_dir: Path,
    *,
    subdir: str = "object_types",
    spec: type = ObjectTypeDef,
    kind: str = "object type",
) -> dict[str, Any]:
    """Load a directory of one-definition-per-file YAML documents."""
    loaded: dict[str, Any] = {}
    for path in _iter_files(schema_dir / subdir, "*.yaml"):
        data = _read_yaml(path)
        if not isinstance(data, dict):
            raise SchemaError(f"{path.name}: expected a mapping at the document root")
        definition = _profile(spec, data, path.name)
        _ensure_unique(loaded, definition.apiName, path.name, kind)
        loaded[definition.apiName] = definition
    return loaded


def _load_collection(path: Path, key: str, spec: type, kind: str) -> dict[str, Any]:
    """Load a list-of-definitions YAML file (functions, links, interfaces)."""
    if not path.exists():
        return {}
    raw = _read_yaml(path)
    entries = raw.get(key, []) if isinstance(raw, dict) else raw
    loaded: dict[str, Any] = {}
    for entry in entries or []:
        definition = _profile(spec, entry, path.name)
        _ensure_unique(loaded, definition.apiName, path.name, kind)
        loaded[definition.apiName] = definition
    return loaded


def _load_agents(schema_dir: Path) -> dict[str, AgentDef]:
    agents: dict[str, AgentDef] = {}
    for path in _iter_files(schema_dir / "agents", "*.yaml"):
        data = _read_yaml(path)
        if not isinstance(data, dict):
            raise SchemaError(f"{path.name}: expected a mapping at the document root")
        if "systemPrompt" not in data and "systemPromptFile" in data:
            prompt_path = schema_dir / str(data.pop("systemPromptFile"))
            if not prompt_path.exists():
                raise SchemaError(f"{path.name}: systemPromptFile {prompt_path} not found")
            data["systemPrompt"] = prompt_path.read_text(encoding="utf-8")
        agent = _profile(AgentDef, data, path.name)
        _ensure_unique(agents, agent.apiName, path.name, "agent")
        agents[agent.apiName] = agent
    return agents


def _load_interfaces(schema_dir: Path) -> dict[str, dict[str, Any]]:
    """Reserved: names only, no runtime semantics in v1."""
    path = schema_dir / "interfaces.yaml"
    if not path.exists():
        return {}
    raw = _read_yaml(path)
    entries = raw.get("interfaces", []) if isinstance(raw, dict) else raw
    interfaces: dict[str, dict[str, Any]] = {}
    for entry in entries or []:
        name = entry.get("apiName")
        if not name:
            raise SchemaError(f"{path.name}: interface entry is missing apiName")
        _ensure_unique(interfaces, name, path.name, "interface")
        interfaces[name] = entry
    return interfaces


def _ensure_unique(seen: dict[str, Any], name: str, source: str, kind: str) -> None:
    if name in seen:
        raise SchemaError(f"{source}: duplicate {kind} apiName {name!r}")


def _validate_references(bundle: SchemaBundle) -> None:
    object_types = bundle.object_types

    # Object-type property references.
    for obj in object_types.values():
        for prop in obj.properties.values():
            if prop.objectType and prop.objectType not in object_types:
                raise SchemaError(
                    f"object type {obj.apiName!r}: property {prop.apiName!r} references "
                    f"unknown object type {prop.objectType!r}"
                )
        for interface in obj.interfaceRefs:
            if interface not in bundle.interfaces:
                raise SchemaError(f"object type {obj.apiName!r}: unknown interface {interface!r}")

    # Link endpoints.
    for link in bundle.link_types.values():
        for side, type_name in (("from", link.fromObjectType), ("to", link.toObjectType)):
            if type_name not in object_types:
                raise SchemaError(
                    f"link type {link.apiName!r}: {side} object type {type_name!r} is not declared"
                )
        _validate_link_name_collisions(bundle, link)

    # Action parameters, rules, and validators.
    for action in bundle.action_types.values():
        for param in action.parameters.values():
            if param.objectType and param.objectType not in object_types:
                raise SchemaError(
                    f"action {action.apiName!r}: parameter {param.apiName!r} references "
                    f"unknown object type {param.objectType!r}"
                )
        function_name = action.function_name()
        if function_name and function_name not in bundle.functions:
            raise SchemaError(
                f"action {action.apiName!r}: runFunction references "
                f"unknown function {function_name!r}"
            )
        _validate_action_rules(bundle, action)

    # Functions.
    for fn in bundle.functions.values():
        for param in fn.parameters.values():
            if param.objectType and param.objectType not in object_types:
                raise SchemaError(
                    f"function {fn.apiName!r}: parameter {param.apiName!r} references "
                    f"unknown object type {param.objectType!r}"
                )
        if not fn.implementation:
            raise SchemaError(f"function {fn.apiName!r}: implementation path is empty")

    # Agents.
    for agent in bundle.agents.values():
        for action_name in agent.allowedActionTypes:
            allowed_action = bundle.action_types.get(action_name)
            if allowed_action is None:
                raise SchemaError(f"agent {agent.apiName!r}: unknown action type {action_name!r}")
            if not allowed_action.agentProposable:
                raise SchemaError(
                    f"agent {agent.apiName!r}: action {action_name!r} is not agent-proposable"
                )
        for fn_name in agent.allowedFunctions:
            allowed_fn = bundle.functions.get(fn_name)
            if allowed_fn is None:
                raise SchemaError(f"agent {agent.apiName!r}: unknown function {fn_name!r}")
            if allowed_fn.kind is not FunctionKind.READ:
                raise SchemaError(
                    f"agent {agent.apiName!r}: function {fn_name!r} is a write function; "
                    "agents may only call read functions"
                )
        if agent.maxTurns < 1:
            raise SchemaError(f"agent {agent.apiName!r}: maxTurns must be >= 1")


def _validate_link_name_collisions(bundle: SchemaBundle, link: LinkTypeDef) -> None:
    """Guarantee that a link name on an object type resolves to exactly one link type."""
    for object_type, name in (
        (link.fromObjectType, link.source_link_name()),
        (link.toObjectType, link.target_link_name()),
    ):
        for other in bundle.link_types.values():
            if other.apiName == link.apiName:
                continue
            other_names = []
            if other.fromObjectType == object_type:
                other_names.append(other.source_link_name())
            if other.toObjectType == object_type:
                other_names.append(other.target_link_name())
            if name in other_names:
                raise SchemaError(
                    f"link type {link.apiName!r}: link name {name!r} on {object_type!r} "
                    f"collides with link type {other.apiName!r}"
                )


def _validate_action_rules(bundle: SchemaBundle, action: ActionTypeDef) -> None:
    from ontology_runtime.meta import (
        CreateLinkRule,
        CreateObjectRule,
        DeleteLinkRule,
        DeleteObjectRule,
        ModifyObjectRule,
    )

    for rule in action.rules:
        if isinstance(rule, CreateObjectRule | ModifyObjectRule | DeleteObjectRule):
            target_type = (
                rule.objectType if isinstance(rule, CreateObjectRule) else rule.target.objectType
            )
            if target_type and target_type not in bundle.object_types:
                raise SchemaError(
                    f"action {action.apiName!r}: rule targets unknown object type {target_type!r}"
                )
            if isinstance(rule, CreateObjectRule):
                obj = bundle.object_types.get(target_type or "")
                if obj:
                    unknown = set(rule.properties) - set(obj.properties)
                    if unknown:
                        raise SchemaError(
                            f"action {action.apiName!r}: createObject rule sets unknown "
                            f"properties {sorted(unknown)} on {target_type}"
                        )
            if isinstance(rule, ModifyObjectRule):
                obj = bundle.object_types.get(target_type or "")
                if obj:
                    unknown = {p.property for p in rule.properties} - set(obj.properties)
                    if unknown:
                        raise SchemaError(
                            f"action {action.apiName!r}: modifyObject rule sets unknown "
                            f"properties {sorted(unknown)} on {target_type}"
                        )
        elif isinstance(rule, CreateLinkRule | DeleteLinkRule):
            link = bundle.link_types.get(rule.linkType)
            if link is None:
                raise SchemaError(
                    f"action {action.apiName!r}: rule references "
                    f"unknown link type {rule.linkType!r}"
                )
            for param_name in (rule.fromParam, rule.toParam):
                param = action.parameters.get(param_name)
                if param and param.type not in (ParameterType.OBJECT_REF, ParameterType.OBJECT_SET):
                    raise SchemaError(
                        f"action {action.apiName!r}: link rule parameter {param_name!r} "
                        "must be objectRef or objectSet"
                    )
