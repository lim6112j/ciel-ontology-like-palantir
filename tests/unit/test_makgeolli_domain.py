"""The shipped makgeolli domain loads and is internally consistent."""

from __future__ import annotations

import pytest

from ontology_runtime.registry import SchemaRegistry

EXPECTED_OBJECT_TYPES = {
    "ActionProposal",
    "AgentRun",
    "Batch",
    "Customer",
    "OutletStock",
    "Product",
    "RawMaterial",
    "SalesOrder",
    "SalesOrderLine",
    "Shipment",
    "Tank",
    "TempReading",
    "WasteRecord",
    "WarehouseStock",
}

EXPECTED_PROPOSABLE = {
    "CreateBatch",
    "CompleteFermentation",
    "CompleteAging",
    "ShipBatch",
    "ReceiveShipment",
    "WasteBatch",
    "CreateSalesOrder",
    "RecordTempReading",
    "AdjustBatchTemp",
    "ConfirmSalesOrder",
    "CancelSalesOrder",
}


@pytest.fixture(scope="module")
def registry() -> SchemaRegistry:
    return SchemaRegistry.from_domain("makgeolli")


def test_all_object_types_present(registry: SchemaRegistry) -> None:
    assert set(registry.bundle.object_types) == EXPECTED_OBJECT_TYPES


def test_inverse_links_are_derived(registry: SchemaRegistry) -> None:
    assert registry.link_on("Product", "batches").is_forward is True
    assert registry.link_on("Batch", "product").is_forward is False
    assert registry.link_on("Tank", "batches").is_forward is True
    assert registry.link_on("Batch", "tank").is_forward is False
    assert registry.link_on("SalesOrder", "lines").is_forward is True
    assert registry.link_on("SalesOrderLine", "order").is_forward is False
    assert registry.link_on("TempReading", "batch").is_forward is False


def test_every_object_type_has_at_least_one_link(registry: SchemaRegistry) -> None:
    for name in registry.bundle.object_types:
        assert registry.links_of(name), f"{name} has no links"


def test_state_machines_are_complete(registry: SchemaRegistry) -> None:
    batch = registry.object_type("Batch").stateMachine
    assert batch is not None
    assert batch.allows("fermenting", "aging")
    assert batch.allows("aging", "ready")
    assert batch.allows("ready", "shipped")
    assert batch.allows("ready", "wasted")
    assert batch.allows("fermenting", "wasted")
    # A batch can never skip bottling: no fermenting→ready shortcut.
    assert not batch.allows("fermenting", "ready")
    assert not batch.allows("aging", "shipped")

    shipment = registry.object_type("Shipment").stateMachine
    assert shipment is not None
    assert shipment.allows("in_transit", "delivered")
    assert not shipment.allows("delivered", "in_transit")

    tank = registry.object_type("Tank").stateMachine
    assert tank is not None
    assert tank.allows("idle", "in_use")
    assert tank.allows("in_use", "cleaning")


def test_agent_writable_actions_exist(registry: SchemaRegistry) -> None:
    proposable = {
        name for name, action in registry.bundle.action_types.items() if action.agentProposable
    }
    assert proposable >= EXPECTED_PROPOSABLE
    # Master data and stock adjustments are operator-only.
    assert "UpsertProduct" not in proposable
    assert "UpsertCustomer" not in proposable
    assert "AdjustWarehouseStock" not in proposable
    assert "RestockMaterial" not in proposable
    # Approval itself must never be agent-proposable.
    assert "ApproveActionProposal" not in proposable
    assert "RejectActionProposal" not in proposable


def test_function_backed_actions_resolve(registry: SchemaRegistry) -> None:
    for action in registry.bundle.action_types.values():
        if action.is_function_backed():
            assert action.function_name() in registry.bundle.functions


def test_write_functions_are_not_agent_callable(registry: SchemaRegistry) -> None:
    for fn in registry.bundle.functions.values():
        if fn.kind.value == "write":
            assert fn.agentCallable is False
            assert fn.apiName not in {
                f for a in registry.bundle.agents.values() for f in a.allowedFunctions
            }


def test_agents_reference_known_actions_and_functions(registry: SchemaRegistry) -> None:
    assert set(registry.bundle.agents) == {
        "brewPlannerAgent",
        "salesIntakeAgent",
        "breweryOpsAgent",
    }
    for agent in registry.bundle.agents.values():
        for action in agent.allowedActionTypes:
            assert action in registry.bundle.action_types
        for fn in agent.allowedFunctions:
            definition = registry.bundle.functions[fn]
            assert definition.kind.value == "read", "agents may only call read functions"


def test_date_indexes_avoid_non_immutable_casts(registry: SchemaRegistry) -> None:
    specs = {spec.name: spec for spec in registry.indexes()}
    brew_date = specs["ix_makgeolli_batch_brewdate"]
    assert "::date" not in brew_date.ddl()
    assert brew_date.expressions == ("(properties->>'brewDate')",)


def test_index_declarations_are_valid(registry: SchemaRegistry) -> None:
    names = [spec.name for spec in registry.indexes()]
    assert len(names) == len(set(names)), "index names must be unique"
    assert "ix_makgeolli_warehousestock_batchrid" in names
    assert "ix_makgeolli_outletstock_customerproduct" in names


def test_internal_types_marked(registry: SchemaRegistry) -> None:
    assert registry.object_type("ActionProposal").internal is True
    assert registry.object_type("AgentRun").internal is True
    assert registry.object_type("Batch").internal is False


def test_shelf_life_is_capped_at_30_days(registry: SchemaRegistry) -> None:
    property = registry.object_type("Product").properties["shelfLifeDays"]
    assert property.max == 30
    assert property.min == 1
