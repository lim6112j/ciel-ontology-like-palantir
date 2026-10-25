"""Ontology metadata endpoints (OSDK-shaped)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from ontology_runtime.api.errors import envelope
from ontology_runtime.registry import SchemaRegistry

router = APIRouter(prefix="/api/ontology", tags=["ontology"])


def _registry(request: Request) -> SchemaRegistry:
    registry: SchemaRegistry = request.app.state.registry
    return registry


@router.get("/objectTypes")
async def list_object_types(request: Request) -> dict[str, Any]:
    registry = _registry(request)
    data = []
    for obj in registry.bundle.object_types.values():
        data.append(
            {
                "apiName": obj.apiName,
                "displayName": obj.displayName,
                "pluralDisplayName": obj.pluralDisplayName,
                "description": obj.description,
                "primaryKey": obj.primaryKey,
                "internal": obj.internal,
                "propertyCount": len(obj.properties),
                "links": [
                    {
                        "apiName": view.link_name,
                        "targetType": view.target_type,
                        "cardinality": view.cardinality.value,
                    }
                    for view in registry.links_of(obj.apiName)
                ],
            }
        )
    return envelope(data, meta={"count": len(data)})


@router.get("/objectTypes/{api_name}")
async def get_object_type(request: Request, api_name: str) -> dict[str, Any]:
    registry = _registry(request)
    obj = registry.object_type(api_name)
    return envelope(
        {
            "apiName": obj.apiName,
            "displayName": obj.displayName,
            "description": obj.description,
            "primaryKey": obj.primaryKey,
            "internal": obj.internal,
            "properties": {
                name: {
                    "apiName": prop.apiName,
                    "displayName": prop.displayName,
                    "type": prop.type.value,
                    "required": prop.required,
                    "indexed": prop.indexed,
                    "unique": prop.unique,
                    "values": prop.values,
                    "objectType": prop.objectType,
                    "description": prop.description,
                }
                for name, prop in obj.properties.items()
            },
            "stateMachine": obj.stateMachine.model_dump(by_alias=True)
            if obj.stateMachine
            else None,
            "invariants": [inv.model_dump() for inv in obj.invariants],
            "links": [
                {
                    "apiName": view.link_name,
                    "targetType": view.target_type,
                    "cardinality": view.cardinality.value,
                    "linkType": view.link.apiName,
                }
                for view in registry.links_of(obj.apiName)
            ],
        }
    )


@router.get("/linkTypes")
async def list_link_types(request: Request) -> dict[str, Any]:
    registry = _registry(request)
    data = [
        {
            "apiName": link.apiName,
            "displayName": link.displayName,
            "fromObjectType": link.fromObjectType,
            "fromApiName": link.source_link_name(),
            "fromCardinality": link.fromCardinality.value,
            "toObjectType": link.toObjectType,
            "toApiName": link.target_link_name(),
            "toCardinality": link.toCardinality.value,
        }
        for link in registry.bundle.link_types.values()
    ]
    return envelope(data, meta={"count": len(data)})


@router.get("/actionTypes")
async def list_action_types(request: Request) -> dict[str, Any]:
    registry = _registry(request)
    data = [
        {
            "apiName": action.apiName,
            "displayName": action.displayName,
            "description": action.description,
            "agentProposable": action.agentProposable,
            "functionBacked": action.is_function_backed(),
            "allowedRoles": action.allowedRoles,
        }
        for action in registry.bundle.action_types.values()
    ]
    return envelope(data, meta={"count": len(data)})


@router.get("/actionTypes/{api_name}")
async def get_action_type(request: Request, api_name: str) -> dict[str, Any]:
    registry = _registry(request)
    action = registry.action_type(api_name)
    return envelope(
        {
            "apiName": action.apiName,
            "displayName": action.displayName,
            "description": action.description,
            "agentProposable": action.agentProposable,
            "functionBacked": action.is_function_backed(),
            "allowedRoles": action.allowedRoles,
            "parameters": {
                name: {
                    "apiName": param.apiName,
                    "type": param.type.value,
                    "required": param.required,
                    "objectType": param.objectType,
                    "values": param.values,
                    "description": param.description,
                    "defaultValue": param.defaultValue,
                }
                for name, param in action.parameters.items()
            },
            "rules": [rule.model_dump(exclude_none=True) for rule in action.rules],
            "validators": [v.model_dump(exclude_none=True) for v in action.validators],
        }
    )


@router.get("/functions")
async def list_functions(request: Request) -> dict[str, Any]:
    registry = _registry(request)
    data = [
        {
            "apiName": fn.apiName,
            "displayName": fn.displayName,
            "description": fn.description,
            "kind": fn.kind.value,
            "agentCallable": fn.agentCallable,
            "parameters": {
                name: {"type": p.type.value, "required": p.required, "objectType": p.objectType}
                for name, p in fn.parameters.items()
            },
        }
        for fn in registry.bundle.functions.values()
    ]
    return envelope(data, meta={"count": len(data)})


@router.get("/agents")
async def list_agents(request: Request) -> dict[str, Any]:
    registry = _registry(request)
    data = [
        {
            "apiName": agent.apiName,
            "displayName": agent.displayName,
            "description": agent.description,
            "kind": agent.kind.value,
            "model": agent.model,
            "allowedActionTypes": agent.allowedActionTypes,
            "allowedFunctions": agent.allowedFunctions,
            "maxTurns": agent.maxTurns,
        }
        for agent in registry.bundle.agents.values()
    ]
    return envelope(data, meta={"count": len(data)})
