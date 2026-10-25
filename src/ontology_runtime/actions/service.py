"""Action execution: validate → build edits → apply → audit, one code path."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.actions.context import EditContext
from ontology_runtime.actions.edits import (
    EDIT_KIND_OF,
    Edit,
    EditBatch,
    LinkCreate,
    LinkDelete,
    ObjectCreate,
    ObjectDelete,
    ObjectModify,
)
from ontology_runtime.db.models import ActionEditRow, ActionRunRow, LinkRow, ObjectRow
from ontology_runtime.errors import (
    IdempotencyConflict,
    NotFoundError,
    ValidationFailed,
)
from ontology_runtime.meta import (
    ActionTypeDef,
    CreateLinkRule,
    CreateObjectRule,
    DeleteLinkRule,
    DeleteObjectRule,
    ModifyObjectRule,
    ModifyPropertyDef,
    ObjectSelector,
    ObjectTypeDef,
    ParameterDef,
    ParameterType,
    RunFunctionRule,
)
from ontology_runtime.registry import SchemaRegistry
from ontology_runtime.validation.violations import ViolationList

_RID_PREFIX = "ri."


@dataclass
class ActionResult:
    run_id: uuid.UUID
    action_type: str
    status: str
    data: dict[str, Any] = field(default_factory=dict)
    violations: list[dict[str, Any]] = field(default_factory=list)
    replayed: bool = False
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "runId": str(self.run_id),
            "actionType": self.action_type,
            "status": self.status,
            "data": self.data,
            "violations": self.violations,
            "replayed": self.replayed,
            "dryRun": self.dry_run,
        }


@dataclass
class ActionRequest:
    action_type: str
    params: dict[str, Any]
    actor: str = "unknown"
    idempotency_key: str | None = None
    dry_run: bool = False


class ActionService:
    def __init__(
        self,
        registry: SchemaRegistry,
        session: AsyncSession,
        *,
        function_executor: Any = None,
    ) -> None:
        self.registry = registry
        self.session = session
        if function_executor is None:
            from ontology_runtime.functions.executor import FunctionExecutor

            function_executor = FunctionExecutor(registry)
        self.functions = function_executor

    # -- public API --------------------------------------------------------
    async def validate(self, request: ActionRequest) -> ActionResult:
        request.dry_run = True
        return await self._run(request)

    async def apply(self, request: ActionRequest) -> ActionResult:
        request.dry_run = False
        if request.idempotency_key:
            replay = await self._replay(request)
            if replay is not None:
                return replay
        return await self._run(request)

    # -- pipeline ----------------------------------------------------------
    async def _run(self, request: ActionRequest) -> ActionResult:
        action = self.registry.action_type(request.action_type)
        run_id = uuid.uuid4()
        violations = ViolationList()

        # 1. Parameter schema + declarative validators.
        params = self._validate_parameters(action, request.params, violations)
        if not violations.ok:
            return await self._reject(request, action, run_id, violations)

        # 2. Build the edit batch against an overlay context.
        context = EditContext(self.registry, self.session, actor=request.actor, params=params)
        if self.functions is not None:
            context.scratch["__function_executor__"] = self.functions.execute_write
        try:
            await self._execute_rules(action, context, params, violations)
        except ValidationFailed as exc:
            return await self._reject(request, action, run_id, _from_dicts(exc.violations))
        except NotFoundError as exc:
            violations.add("not_found", "", exc.message)
            return await self._reject(request, action, run_id, violations)

        if not violations.ok:
            return await self._reject(request, action, run_id, violations)

        # 3. Object invariants + state-machine preconditions on post-overlay state.
        await self._check_invariants(context, violations)
        if not violations.ok:
            return await self._reject(request, action, run_id, violations)

        if request.dry_run:
            return ActionResult(
                run_id=run_id,
                action_type=action.apiName,
                status="validated",
                data={"editCount": len(context.batch), **_summarize(context.batch)},
                dry_run=True,
            )

        # 4. Apply, audit, commit.
        try:
            run = await self._persist(request, action, run_id, context.batch)
        except IdempotencyReplay as replay:
            await self.session.rollback()
            return replay.result

        return ActionResult(
            run_id=run.id,
            action_type=action.apiName,
            status="succeeded",
            data={"editCount": len(context.batch), **_summarize(context.batch)},
        )

    # -- parameter validation ---------------------------------------------
    def _validate_parameters(
        self, action: ActionTypeDef, raw: dict[str, Any], violations: ViolationList
    ) -> dict[str, Any]:
        unknown = set(raw) - set(action.parameters)
        for name in sorted(unknown):
            violations.add("unknown_parameter", name, f"{action.apiName} has no parameter {name!r}")

        params: dict[str, Any] = {}
        for name, spec in action.parameters.items():
            if name in raw:
                value = raw[name]
            elif spec.defaultValue is not None:
                value = spec.defaultValue
            elif spec.required:
                violations.add("missing_parameter", name, f"parameter {name!r} is required")
                continue
            else:
                continue
            coerced = _coerce_parameter(spec, value, violations)
            if coerced is not _INVALID:
                params[name] = coerced

        self._run_validators(action, params, violations)
        return params

    def _run_validators(
        self, action: ActionTypeDef, params: dict[str, Any], violations: ViolationList
    ) -> None:
        for validator in action.validators:
            value = params.get(validator.field)
            message = validator.message
            if validator.rule == "required" and (value is None or value in ("", [])):
                violations.add(
                    "required", validator.field, message or f"{validator.field} is required"
                )
            elif validator.rule == "range" and value is not None:
                bounds = validator.value or {}
                low, high = bounds.get("min"), bounds.get("max")
                if low is not None and value < low:
                    violations.add(
                        "range", validator.field, message or f"{validator.field} must be >= {low}"
                    )
                if high is not None and value > high:
                    violations.add(
                        "range", validator.field, message or f"{validator.field} must be <= {high}"
                    )
            elif validator.rule == "regex" and value is not None:
                if not re.fullmatch(str(validator.value), str(value)):
                    violations.add(
                        "regex", validator.field, message or f"{validator.field} has invalid format"
                    )
            elif validator.rule == "enum" and value is not None:
                allowed = validator.value or []
                if value not in allowed:
                    violations.add(
                        "enum",
                        validator.field,
                        message or f"{validator.field} must be one of {allowed}",
                    )
            elif validator.rule == "compare" and validator.other:
                other = params.get(validator.other)
                if value is not None and other is not None and value > other:
                    violations.add(
                        "compare",
                        validator.field,
                        message or f"{validator.field} must not exceed {validator.other}",
                    )
            elif (
                validator.rule == "exists"
                and value is not None
                and isinstance(value, str)
                and not value.startswith(_RID_PREFIX)
            ):
                violations.add(
                    "exists", validator.field, f"{validator.field} must be an object rid"
                )

    # -- rule execution ----------------------------------------------------
    async def _execute_rules(
        self,
        action: ActionTypeDef,
        context: EditContext,
        params: dict[str, Any],
        violations: ViolationList,
    ) -> None:
        if action.is_function_backed():
            function_name = action.function_name()
            assert function_name is not None
            if self.functions is None:
                violations.add(
                    "function_unavailable", "", f"function {function_name!r} is not registered"
                )
                return
            await self.functions.execute_write(function_name, context, params)
            return

        for rule in action.rules:
            if isinstance(rule, CreateObjectRule):
                await self._apply_create(rule, context, params, violations)
            elif isinstance(rule, ModifyObjectRule):
                await self._apply_modify(rule, context, params, violations)
            elif isinstance(rule, DeleteObjectRule):
                await self._apply_delete(rule, context, params, violations)
            elif isinstance(rule, CreateLinkRule):
                self._apply_create_link(rule, context, params, violations)
            elif isinstance(rule, DeleteLinkRule):
                self._apply_delete_link(rule, context, params, violations)
            elif isinstance(rule, RunFunctionRule):  # pragma: no cover - validated as exclusive
                violations.add("invalid_rule", rule.type, "runFunction must be the only rule")

    async def _apply_create(
        self,
        rule: CreateObjectRule,
        context: EditContext,
        params: dict[str, Any],
        violations: ViolationList,
    ) -> None:
        properties = _resolve_property_values(
            rule.objectType, rule.properties, params, self.registry
        )
        rid = context.create(rule.objectType, properties)
        context.scratch[f"created:{rule.objectType}"] = rid
        if rule.assignRidTo:
            context.scratch[rule.assignRidTo] = rid

    async def _apply_modify(
        self,
        rule: ModifyObjectRule,
        context: EditContext,
        params: dict[str, Any],
        violations: ViolationList,
    ) -> None:
        rids = await self._resolve_targets(rule.target, context, params)
        if not rids:
            violations.add("target_not_found", "target", "no target object for modify rule")
            return
        for rid in rids:
            current = await context.require(rid)
            if rule.expectedStatus:
                state_prop = _state_property(self.registry.object_type(current.object_type))
                status = current.properties.get(state_prop) if state_prop else None
                if status not in rule.expectedStatus:
                    violations.add(
                        "invalid_state",
                        state_prop or "status",
                        f"{current.object_type} {rid} is in state {status!r}; "
                        f"expected one of {rule.expectedStatus}",
                        objectType=current.object_type,
                        objectRef=rid,
                    )
                    continue
            updates = _resolve_modify_values(rule.properties, params)
            await context.modify(rid, updates)

    async def _apply_delete(
        self,
        rule: DeleteObjectRule,
        context: EditContext,
        params: dict[str, Any],
        violations: ViolationList,
    ) -> None:
        for rid in await self._resolve_targets(rule.target, context, params):
            await context.delete(rid)

    def _apply_create_link(
        self,
        rule: CreateLinkRule,
        context: EditContext,
        params: dict[str, Any],
        violations: ViolationList,
    ) -> None:
        from_rids = _as_rid_list(params.get(rule.fromParam))
        to_rids = _as_rid_list(params.get(rule.toParam))
        if not from_rids or not to_rids:
            violations.add(
                "missing_link_endpoint", rule.linkType, "link rule has an empty endpoint"
            )
            return
        for from_rid in from_rids:
            for to_rid in to_rids:
                context.link(rule.linkType, from_rid, to_rid)

    def _apply_delete_link(
        self,
        rule: DeleteLinkRule,
        context: EditContext,
        params: dict[str, Any],
        violations: ViolationList,
    ) -> None:
        for from_rid in _as_rid_list(params.get(rule.fromParam)):
            for to_rid in _as_rid_list(params.get(rule.toParam)):
                context.unlink(rule.linkType, from_rid, to_rid)

    async def _resolve_targets(
        self, selector: ObjectSelector, context: EditContext, params: dict[str, Any]
    ) -> list[str]:
        if selector.param is None:
            return []
        value = params.get(selector.param)
        return _as_rid_list(value)

    # -- invariants --------------------------------------------------------
    async def _check_invariants(self, context: EditContext, violations: ViolationList) -> None:
        from ontology_runtime.validation.invariants import INVARIANTS

        checked: set[str] = set()
        for edit in context.batch:
            if isinstance(edit, ObjectCreate | ObjectModify):
                checked.add(edit.object_type)
        for object_type in checked:
            obj_def = self.registry.object_type(object_type)
            for invariant in obj_def.invariants:
                implementation = INVARIANTS.get(invariant.apiName)
                if implementation is None:
                    violations.add(
                        "unknown_invariant",
                        invariant.apiName,
                        f"invariant {invariant.apiName!r} is not implemented",
                    )
                    continue
                await implementation(context, violations, **invariant.params)

    # -- persistence -------------------------------------------------------
    async def _persist(
        self,
        request: ActionRequest,
        action: ActionTypeDef,
        run_id: uuid.UUID,
        batch: EditBatch,
    ) -> ActionRunRow:
        run = ActionRunRow(
            id=run_id,
            action_type=action.apiName,
            actor=request.actor,
            idempotency_key=request.idempotency_key,
            params_hash=_params_hash(request.params) if request.idempotency_key else None,
            status="succeeded",
            dry_run=False,
            params=_jsonable(request.params),
            proposal_rid=_proposal_rid(action, request.params),
        )
        if request.idempotency_key:
            existing = await self.session.scalar(
                select(ActionRunRow).where(ActionRunRow.idempotency_key == request.idempotency_key)
            )
            if existing is not None:
                if existing.params_hash != run.params_hash:
                    raise IdempotencyConflict(
                        "idempotency key was already used with different parameters"
                    )
                raise IdempotencyReplay(
                    ActionResult(
                        run_id=existing.id,
                        action_type=existing.action_type,
                        status=existing.status,
                        data=existing.result or {},
                        violations=(existing.error or {}).get("violations", []),
                        replayed=True,
                    )
                )

        self.session.add(run)
        await self.session.flush()

        for seq, edit in enumerate(batch, start=1):
            await self._apply_edit(edit)
            self.session.add(
                ActionEditRow(
                    run_id=run.id,
                    seq=seq,
                    edit_kind=EDIT_KIND_OF[type(edit)].value,
                    object_type=_edit_object_type(edit),
                    rid=_edit_rid(edit),
                    before=_edit_before(edit),
                    after=_edit_after(edit),
                )
            )
        await self.session.flush()
        return run

    async def _apply_edit(self, edit: Edit) -> None:
        from ontology_runtime.store.link_store import LinkStore

        if isinstance(edit, ObjectCreate):
            self.session.add(
                ObjectRow(
                    rid=edit.rid,
                    object_type=edit.object_type,
                    properties=edit.properties,
                    version=1,
                )
            )
            await self.session.flush()
        elif isinstance(edit, ObjectModify):
            row = await self.session.get(ObjectRow, edit.rid, with_for_update=True)
            if row is None or row.deleted_at is not None:
                raise NotFoundError(f"object {edit.rid!r} disappeared during apply")
            merged = {**row.properties, **edit.properties}
            merged = {k: v for k, v in merged.items() if v is not None}
            row.properties = merged
            row.version = row.version + 1
            row.updated_at = dt.datetime.now(dt.UTC)
            await self.session.flush()
        elif isinstance(edit, ObjectDelete):
            row = await self.session.get(ObjectRow, edit.rid, with_for_update=True)
            if row is not None:
                row.deleted_at = dt.datetime.now(dt.UTC)
                row.version = row.version + 1
                await self.session.flush()
        elif isinstance(edit, LinkCreate):
            await LinkStore(self.registry, self.session).create(
                edit.link_type, edit.from_rid, edit.to_rid
            )
        elif isinstance(edit, LinkDelete):
            await self.session.execute(
                delete(LinkRow)
                .where(LinkRow.link_type == edit.link_type)
                .where(LinkRow.from_rid == edit.from_rid)
                .where(LinkRow.to_rid == edit.to_rid)
            )
            await self.session.flush()

    async def _reject(
        self,
        request: ActionRequest,
        action: ActionTypeDef,
        run_id: uuid.UUID,
        violations: ViolationList,
    ) -> ActionResult:
        if not request.dry_run:
            run = ActionRunRow(
                id=run_id,
                action_type=action.apiName,
                actor=request.actor,
                idempotency_key=None,
                status="failed",
                dry_run=False,
                params=_jsonable(request.params),
                error={"violations": violations.to_dicts()},
            )
            self.session.add(run)
            await self.session.flush()
        return ActionResult(
            run_id=run_id,
            action_type=action.apiName,
            status="failed",
            violations=violations.to_dicts(),
            dry_run=request.dry_run,
        )

    async def _replay(self, request: ActionRequest) -> ActionResult | None:
        existing = await self.session.scalar(
            select(ActionRunRow).where(ActionRunRow.idempotency_key == request.idempotency_key)
        )
        if existing is None:
            return None
        if existing.params_hash != _params_hash(request.params):
            raise IdempotencyConflict("idempotency key was already used with different parameters")
        return ActionResult(
            run_id=existing.id,
            action_type=existing.action_type,
            status=existing.status,
            data=existing.result or {},
            violations=(existing.error or {}).get("violations", []),
            replayed=True,
        )


class IdempotencyReplay(Exception):
    """Raised when a concurrent duplicate key was already committed."""

    def __init__(self, result: ActionResult) -> None:
        self.result = result


_INVALID = object()


def _coerce_integer(spec: ParameterDef, value: Any) -> Any:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("expected an integer")
    return value


def _coerce_decimal(spec: ParameterDef, value: Any) -> Any:
    del spec
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("expected a number")
    return value


def _coerce_boolean(spec: ParameterDef, value: Any) -> Any:
    del spec
    if not isinstance(value, bool):
        raise ValueError("expected a boolean")
    return value


def _coerce_date(spec: ParameterDef, value: Any) -> Any:
    del spec
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    return dt.date.fromisoformat(str(value)).isoformat()


def _coerce_timestamp(spec: ParameterDef, value: Any) -> Any:
    del spec
    return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).isoformat()


def _coerce_enum(spec: ParameterDef, value: Any) -> Any:
    if value not in (spec.values or []):
        raise ValueError(f"expected one of {spec.values}")
    return value


def _coerce_object_ref(spec: ParameterDef, value: Any) -> Any:
    del spec
    rid = value.get("rid") if isinstance(value, dict) else value
    if not isinstance(rid, str) or not rid.startswith(_RID_PREFIX):
        raise ValueError("expected an object rid")
    return rid


def _coerce_object_set(spec: ParameterDef, value: Any) -> Any:
    del spec
    items = value if isinstance(value, list) else [value]
    rids = []
    for item in items:
        rid = item.get("rid") if isinstance(item, dict) else item
        if not isinstance(rid, str) or not rid.startswith(_RID_PREFIX):
            raise ValueError("expected a list of object rids")
        rids.append(rid)
    return rids


def _coerce_json(spec: ParameterDef, value: Any) -> Any:
    del spec
    if not isinstance(value, dict | list):
        raise ValueError("expected a JSON object or array")
    return value


def _coerce_text(spec: ParameterDef, value: Any) -> Any:
    del spec
    if not isinstance(value, str):
        raise ValueError("expected a string")
    return value


#: One coercion per parameter type, so each rule stays a few lines.
_COERCERS: dict[ParameterType, Any] = {
    ParameterType.INTEGER: _coerce_integer,
    ParameterType.DECIMAL: _coerce_decimal,
    ParameterType.BOOLEAN: _coerce_boolean,
    ParameterType.DATE: _coerce_date,
    ParameterType.TIMESTAMP: _coerce_timestamp,
    ParameterType.ENUM: _coerce_enum,
    ParameterType.OBJECT_REF: _coerce_object_ref,
    ParameterType.OBJECT_SET: _coerce_object_set,
    ParameterType.JSON: _coerce_json,
    ParameterType.STRING: _coerce_text,
    ParameterType.TEXT: _coerce_text,
}


def _coerce_parameter(spec: ParameterDef, value: Any, violations: ViolationList) -> Any:
    if value is None:
        if spec.required:
            violations.add(
                "missing_parameter", spec.apiName, f"parameter {spec.apiName!r} is required"
            )
        return _INVALID
    coercer = _COERCERS.get(spec.type)
    if coercer is None:  # pragma: no cover - every enum member is mapped
        return value
    try:
        return coercer(spec, value)
    except (ValueError, TypeError) as exc:
        violations.add("invalid_parameter", spec.apiName, f"{spec.apiName}: {exc}")
        return _INVALID


def _resolve_property_values(
    object_type: str,
    properties: dict[str, Any],
    params: dict[str, Any],
    registry: SchemaRegistry,
) -> dict[str, Any]:
    """Turn `{param: x}`, `{literal: x}`, `{prefix: X}`, `{now: true}` into plain values."""
    resolved: dict[str, Any] = {}
    for name, value in properties.items():
        if isinstance(value, dict):
            if "param" in value:
                resolved[name] = params.get(value["param"])
            elif "literal" in value:
                resolved[name] = value["literal"]
            elif value.get("now"):
                resolved[name] = dt.datetime.now(dt.UTC).isoformat()
            elif "prefix" in value:
                resolved[name] = _generate_number(str(value["prefix"]), registry)
            else:
                resolved[name] = value
        else:
            resolved[name] = value
    return resolved


def _generate_number(prefix: str, registry: SchemaRegistry) -> str:
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:4].upper()}"


def _resolve_modify_values(
    properties: list[ModifyPropertyDef],
    params: dict[str, Any],
) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for prop in properties:
        if prop.fromParam:
            updates[prop.property] = params.get(prop.fromParam)
        elif isinstance(prop.value, dict) and prop.value.get("now"):
            updates[prop.property] = dt.datetime.now(dt.UTC).isoformat()
        else:
            updates[prop.property] = prop.value
    return updates


def _state_property(obj_def: ObjectTypeDef) -> str | None:
    return obj_def.stateMachine.property if obj_def.stateMachine else None


def _as_rid_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


def _params_hash(params: dict[str, Any]) -> str:
    blob = json.dumps(_jsonable(params), sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(blob).hexdigest()


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _proposal_rid(action: ActionTypeDef, params: dict[str, Any]) -> str | None:
    """Record which proposal an approval run executed (accepts raw or normalized refs)."""
    if action.apiName != "ApproveActionProposal":
        return None
    value = params.get("proposal")
    if isinstance(value, dict):
        value = value.get("rid")
    return value if isinstance(value, str) else None


def _edit_object_type(edit: Edit) -> str:
    if isinstance(edit, ObjectCreate | ObjectModify | ObjectDelete):
        return edit.object_type
    return ""


def _edit_rid(edit: Edit) -> str:
    """The primary object touched by an edit (link edits report their source)."""
    if isinstance(edit, ObjectCreate | ObjectModify | ObjectDelete):
        return edit.rid
    return edit.from_rid


def _edit_before(edit: Edit) -> dict[str, Any] | None:
    if isinstance(edit, ObjectModify | ObjectDelete):
        return edit.before
    return None


def _edit_after(edit: Edit) -> dict[str, Any] | None:
    if isinstance(edit, (ObjectCreate, ObjectModify)):
        return edit.properties
    if isinstance(edit, LinkCreate | LinkDelete):
        return {"fromRid": edit.from_rid, "toRid": edit.to_rid}
    return None


def _summarize(batch: EditBatch) -> dict[str, Any]:
    created = batch.created_rids_by_type()
    modified = [e.rid for e in batch.edits if isinstance(e, ObjectModify)]
    return {"created": created, "modified": modified}


def _from_dicts(items: list[dict[str, Any]]) -> ViolationList:
    violations = ViolationList()
    for item in items:
        violations.add(
            item.get("code", "error"),
            item.get("path", ""),
            item.get("message", ""),
            objectType=item.get("objectType"),
            objectRef=item.get("objectRef"),
        )
    return violations
