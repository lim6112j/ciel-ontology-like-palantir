"""Action engine: validation parity, transactions, audit, and idempotency."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.actions.service import ActionRequest, ActionService
from ontology_runtime.db.models import ActionEditRow, ActionRunRow, ObjectRow
from ontology_runtime.errors import IdempotencyConflict
from ontology_runtime.registry import SchemaRegistry
from ontology_runtime.store.object_store import ObjectStore


@pytest.fixture
def registry(tmp_path: Path) -> SchemaRegistry:
    """Small schema exercising declarative rules, state machines, and invariants."""
    schema = tmp_path / "schema"
    files = {
        "object_types/Outlet.yaml": {
            "apiName": "Outlet",
            "displayName": "거래처",
            "primaryKey": "outletNo",
            "properties": {
                "outletNo": {
                    "apiName": "outletNo",
                    "type": "string",
                    "required": True,
                    "unique": True,
                },
                "name": {"apiName": "name", "type": "string", "required": True},
                "status": {
                    "apiName": "status",
                    "type": "enum",
                    "values": ["active", "closed"],
                    "required": True,
                },
            },
            "stateMachine": {
                "property": "status",
                "initial": "active",
                "transitions": [
                    {"from": "active", "to": "closed"},
                    {"from": "closed", "to": "active"},
                ],
            },
        },
        "object_types/Order.yaml": {
            "apiName": "Order",
            "displayName": "발주",
            "primaryKey": "orderNo",
            "properties": {
                "orderNo": {
                    "apiName": "orderNo",
                    "type": "string",
                    "required": True,
                    "unique": True,
                },
                "outletRid": {"apiName": "outletRid", "type": "objectRef", "objectType": "Outlet"},
                "status": {
                    "apiName": "status",
                    "type": "enum",
                    "values": ["draft", "submitted"],
                    "required": True,
                },
                "cases": {"apiName": "cases", "type": "integer"},
            },
            "stateMachine": {
                "property": "status",
                "initial": "draft",
                "transitions": [{"from": "draft", "to": "submitted"}],
            },
        },
        "link_types.yaml": {
            "linkTypes": [
                {
                    "apiName": "orders",
                    "displayName": "발주",
                    "fromObjectType": "Outlet",
                    "fromApiName": "orders",
                    "fromCardinality": "many",
                    "toObjectType": "Order",
                    "toApiName": "outlet",
                    "toCardinality": "one",
                }
            ]
        },
        "action_types/CreateOrder.yaml": {
            "apiName": "CreateOrder",
            "displayName": "발주 생성",
            "parameters": {
                "outlet": {"apiName": "outlet", "type": "objectRef", "objectType": "Outlet"},
                "orderNo": {"apiName": "orderNo", "type": "string"},
                "cases": {"apiName": "cases", "type": "integer"},
            },
            "validators": [{"field": "cases", "rule": "range", "value": {"min": 1, "max": 100}}],
            "rules": [
                {
                    "type": "createObject",
                    "objectType": "Order",
                    "properties": {
                        "orderNo": {"param": "orderNo"},
                        "outletRid": {"param": "outlet"},
                        "cases": {"param": "cases"},
                        "status": {"literal": "draft"},
                    },
                }
            ],
        },
        "action_types/SubmitOrder.yaml": {
            "apiName": "SubmitOrder",
            "displayName": "발주 제출",
            "parameters": {
                "order": {"apiName": "order", "type": "objectRef", "objectType": "Order"}
            },
            "rules": [
                {
                    "type": "modifyObject",
                    "target": {"param": "order", "objectType": "Order"},
                    "expectedStatus": ["draft"],
                    "properties": [{"property": "status", "value": "submitted"}],
                }
            ],
        },
        "action_types/CloseOutlet.yaml": {
            "apiName": "CloseOutlet",
            "displayName": "거래처 폐업",
            "parameters": {
                "outlet": {"apiName": "outlet", "type": "objectRef", "objectType": "Outlet"}
            },
            "rules": [
                {
                    "type": "modifyObject",
                    "target": {"param": "outlet", "objectType": "Outlet"},
                    "expectedStatus": ["active"],
                    "properties": [{"property": "status", "value": "closed"}],
                }
            ],
        },
    }
    for relative, payload in files.items():
        path = schema / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    return SchemaRegistry.from_directory(schema)


@pytest.fixture
def service(registry: SchemaRegistry, session: AsyncSession) -> ActionService:
    return ActionService(registry, session)


async def _outlet(registry: SchemaRegistry, session: AsyncSession, no: str = "O-1"):
    return await ObjectStore(registry, session).create(
        "Outlet", {"outletNo": no, "name": "행복식당", "status": "active"}
    )


async def test_create_action_applies_and_audits(
    service: ActionService, registry: SchemaRegistry, session: AsyncSession
) -> None:
    outlet = await _outlet(registry, session)
    result = await service.apply(
        ActionRequest(
            "CreateOrder", {"outlet": outlet.rid, "orderNo": "SO-1", "cases": 10}, actor="rep01"
        )
    )
    assert result.status == "succeeded"
    order = await session.scalar(select(ObjectRow).where(ObjectRow.object_type == "Order"))
    assert order is not None
    assert order.properties["orderNo"] == "SO-1"

    run = await session.get(ActionRunRow, result.run_id)
    assert run is not None
    assert run.actor == "rep01"

    edits = (
        await session.scalars(select(ActionEditRow).where(ActionEditRow.run_id == result.run_id))
    ).all()
    assert {edit.edit_kind for edit in edits} == {"createObject"}
    assert len(edits) == 1


async def test_validate_matches_apply_without_writing(
    service: ActionService, registry: SchemaRegistry, session: AsyncSession
) -> None:
    outlet = await _outlet(registry, session)
    params = {"outlet": outlet.rid, "orderNo": "SO-2", "cases": 3}

    dry = await service.validate(ActionRequest("CreateOrder", params))
    applied = await service.apply(ActionRequest("CreateOrder", params))

    assert dry.data["editCount"] == applied.data["editCount"]
    # RIDs are freshly minted per run; compare the shape, not the identity.
    assert set(dry.data["created"]) == set(applied.data["created"])
    assert len(dry.data["created"]["Order"]) == len(applied.data["created"]["Order"]) == 1
    assert dry.data["modified"] == applied.data["modified"]


async def test_validate_does_not_persist(
    service: ActionService, registry: SchemaRegistry, session: AsyncSession
) -> None:
    outlet = await _outlet(registry, session)
    await service.validate(
        ActionRequest("CreateOrder", {"outlet": outlet.rid, "orderNo": "SO-3", "cases": 1})
    )
    count = await session.scalar(select(func.count()).select_from(ObjectRow))
    assert count == 1  # only the outlet


async def test_missing_parameter_rejected(
    service: ActionService, registry: SchemaRegistry, session: AsyncSession
) -> None:
    outlet = await _outlet(registry, session)
    result = await service.apply(ActionRequest("CreateOrder", {"outlet": outlet.rid}))
    assert result.status == "failed"
    assert {v["path"] for v in result.violations} >= {"orderNo", "cases"}


async def test_unknown_parameter_rejected(
    service: ActionService, registry: SchemaRegistry, session: AsyncSession
) -> None:
    outlet = await _outlet(registry, session)
    result = await service.apply(
        ActionRequest(
            "CreateOrder", {"outlet": outlet.rid, "orderNo": "X", "cases": 1, "ghost": True}
        )
    )
    assert any(v["code"] == "unknown_parameter" for v in result.violations)


async def test_range_validator_enforced(
    service: ActionService, registry: SchemaRegistry, session: AsyncSession
) -> None:
    outlet = await _outlet(registry, session)
    result = await service.apply(
        ActionRequest("CreateOrder", {"outlet": outlet.rid, "orderNo": "SO-9", "cases": 500})
    )
    assert result.status == "failed"
    assert result.violations[0]["code"] == "range"


async def test_state_machine_precondition(
    service: ActionService, registry: SchemaRegistry, session: AsyncSession
) -> None:
    outlet = await _outlet(registry, session)
    created = await service.apply(
        ActionRequest("CreateOrder", {"outlet": outlet.rid, "orderNo": "SO-4", "cases": 1})
    )
    order_rid = created.data["created"]["Order"][0]

    first = await service.apply(ActionRequest("SubmitOrder", {"order": order_rid}))
    assert first.status == "succeeded", first.violations

    second = await service.apply(ActionRequest("SubmitOrder", {"order": order_rid}))
    assert second.status == "failed"
    assert second.violations[0]["code"] == "invalid_state"


async def test_failed_action_persists_no_edits(
    service: ActionService, registry: SchemaRegistry, session: AsyncSession
) -> None:
    outlet = await _outlet(registry, session)
    await service.apply(
        ActionRequest("CreateOrder", {"outlet": outlet.rid, "orderNo": "SO-5", "cases": 0})
    )
    edits = await session.scalar(select(func.count()).select_from(ActionEditRow))
    assert edits == 0
    orders = await session.scalar(
        select(func.count()).select_from(ObjectRow).where(ObjectRow.object_type == "Order")
    )
    assert orders == 0


async def test_idempotent_replay_returns_same_result(
    service: ActionService, registry: SchemaRegistry, session: AsyncSession
) -> None:
    outlet = await _outlet(registry, session)
    request = ActionRequest(
        "CreateOrder",
        {"outlet": outlet.rid, "orderNo": "SO-6", "cases": 2},
        idempotency_key="key-1",
    )
    first = await service.apply(request)
    second = await service.apply(request)
    assert second.replayed is True
    assert second.run_id == first.run_id

    orders = await session.scalar(
        select(func.count()).select_from(ObjectRow).where(ObjectRow.object_type == "Order")
    )
    assert orders == 1


async def test_idempotency_key_with_different_params_conflicts(
    service: ActionService, registry: SchemaRegistry, session: AsyncSession
) -> None:
    outlet = await _outlet(registry, session)
    await service.apply(
        ActionRequest(
            "CreateOrder",
            {"outlet": outlet.rid, "orderNo": "SO-7", "cases": 1},
            idempotency_key="key-2",
        )
    )
    with pytest.raises(IdempotencyConflict):
        await service.apply(
            ActionRequest(
                "CreateOrder",
                {"outlet": outlet.rid, "orderNo": "SO-8", "cases": 1},
                idempotency_key="key-2",
            )
        )


async def test_declarative_create_generates_rid(
    service: ActionService, registry: SchemaRegistry, session: AsyncSession
) -> None:
    outlet = await _outlet(registry, session)
    result = await service.apply(
        ActionRequest("CreateOrder", {"outlet": outlet.rid, "orderNo": "SO-10", "cases": 1})
    )
    created = result.data["created"]["Order"]
    assert len(created) == 1
    assert created[0].startswith("ri.liquor.object.order.")
