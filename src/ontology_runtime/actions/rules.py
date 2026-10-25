"""Rule execution shared by the action service and nested verified actions.

Extracted so `ApproveActionProposal` can stage the proposed action's edits into
the *same* EditBatch instead of starting a second transaction.
"""

from __future__ import annotations

from typing import Any

from ontology_runtime.actions.context import EditContext
from ontology_runtime.errors import ValidationFailed
from ontology_runtime.meta import (
    ActionTypeDef,
    CreateLinkRule,
    CreateObjectRule,
    DeleteLinkRule,
    DeleteObjectRule,
    ModifyObjectRule,
    RunFunctionRule,
)
from ontology_runtime.meta.action_type import property_param_refs


async def build_action_edits(
    context: EditContext,
    action: ActionTypeDef,
    params: dict[str, Any],
) -> None:
    """Stage an action's edits onto the context's EditBatch.

    Functions are resolved through the context's runtime registry when present;
    otherwise a function-backed action raises so the caller sees a clear error.
    """
    if action.is_function_backed():
        function_name = action.function_name()
        assert function_name is not None
        executor = context.scratch.get("__function_executor__")
        if executor is None:
            raise ValidationFailed(
                [
                    {
                        "code": "function_unavailable",
                        "path": "",
                        "message": f"function {function_name!r} is not available in this context",
                    }
                ]
            )
        await executor(function_name, context, params)
        return

    for rule in action.rules:
        if isinstance(rule, CreateObjectRule):
            _build_create(context, rule, params)
        elif isinstance(rule, ModifyObjectRule):
            await _build_modify(context, rule, params)
        elif isinstance(rule, DeleteObjectRule):
            for rid in _rids(params.get(rule.target.param or "")):
                await context.delete(rid)
        elif isinstance(rule, CreateLinkRule):
            for from_rid in _rids(params.get(rule.fromParam)):
                for to_rid in _rids(params.get(rule.toParam)):
                    context.link(rule.linkType, from_rid, to_rid)
        elif isinstance(rule, DeleteLinkRule):
            for from_rid in _rids(params.get(rule.fromParam)):
                for to_rid in _rids(params.get(rule.toParam)):
                    context.unlink(rule.linkType, from_rid, to_rid)
        elif isinstance(rule, RunFunctionRule):  # pragma: no cover - exclusivity enforced
            raise ValidationFailed(
                [
                    {
                        "code": "invalid_rule",
                        "path": "rules",
                        "message": "runFunction must be exclusive",
                    }
                ]
            )


def _build_create(context: EditContext, rule: CreateObjectRule, params: dict[str, Any]) -> None:
    from ontology_runtime.actions.service import _resolve_property_values

    values = _resolve_property_values(rule.objectType, rule.properties, params, context.registry)
    rid = context.create(rule.objectType, values)
    if rule.assignRidTo:
        context.scratch[rule.assignRidTo] = rid
    context.scratch[f"created:{rule.objectType}"] = rid


async def _build_modify(
    context: EditContext, rule: ModifyObjectRule, params: dict[str, Any]
) -> None:
    from ontology_runtime.actions.service import _resolve_modify_values, _state_property

    for rid in _rids(params.get(rule.target.param or "")):
        current = await context.require(rid)
        if rule.expectedStatus:
            state_prop = _state_property(context.registry.object_type(current.object_type))
            current_state = current.properties.get(state_prop) if state_prop else None
            if current_state not in rule.expectedStatus:
                raise ValidationFailed(
                    [
                        {
                            "code": "invalid_state",
                            "path": state_prop or "status",
                            "message": (
                                f"{current.object_type} {rid} is in state {current_state!r}; "
                                f"expected one of {rule.expectedStatus}"
                            ),
                            "objectType": current.object_type,
                            "objectRef": rid,
                        }
                    ]
                )
        await context.modify(rid, _resolve_modify_values(rule.properties, params))


def _rids(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


__all__ = ["build_action_edits", "property_param_refs"]
