"""The shipped v1 ontology loads and is internally consistent."""

from __future__ import annotations

import pytest

from ontology_runtime.config import SCHEMA_DIR
from ontology_runtime.registry import SchemaRegistry

EXPECTED_OBJECT_TYPES = {
    "ActionProposal",
    "AgentRun",
    "Delivery",
    "DeliveryRoute",
    "DeliveryStop",
    "Depot",
    "Driver",
    "DriverShift",
    "InvoiceLine",
    "Outlet",
    "Product",
    "SalesInvoice",
    "SalesOrder",
    "SalesOrderLine",
    "SalesRep",
    "Vehicle",
}


@pytest.fixture(scope="module")
def registry() -> SchemaRegistry:
    return SchemaRegistry.from_directory(SCHEMA_DIR)


def test_all_object_types_present(registry: SchemaRegistry) -> None:
    assert set(registry.bundle.object_types) == EXPECTED_OBJECT_TYPES


def test_inverse_links_are_derived(registry: SchemaRegistry) -> None:
    assert registry.link_on("Delivery", "stops").is_forward is True
    assert registry.link_on("DeliveryStop", "delivery").is_forward is False
    assert registry.link_on("Outlet", "orders").is_forward is True
    assert registry.link_on("SalesOrder", "outlet").is_forward is False


def test_every_object_type_has_at_least_one_link(registry: SchemaRegistry) -> None:
    for name in registry.bundle.object_types:
        assert registry.links_of(name), f"{name} has no links"


def test_state_machines_are_complete(registry: SchemaRegistry) -> None:
    order = registry.object_type("SalesOrder")
    machine = order.stateMachine
    assert machine is not None
    assert machine.allows("draft", "submitted")
    assert not machine.allows("draft", "fulfilled")

    stop = registry.object_type("DeliveryStop").stateMachine
    assert stop is not None
    assert stop.allows("planned", "arrived")
    assert not stop.allows("completed", "planned")


def test_agent_writable_actions_exist(registry: SchemaRegistry) -> None:
    proposable = {
        name for name, action in registry.bundle.action_types.items() if action.agentProposable
    }
    assert {
        "CreateSalesOrder",
        "SubmitSalesOrder",
        "PlanDeliveries",
        "CompleteStop",
        "FailStop",
        "ReassignStop",
    } <= proposable
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


def test_date_indexes_avoid_non_immutable_casts(registry: SchemaRegistry) -> None:
    # `(x)::date` is not IMMUTABLE in PostgreSQL, so it cannot back an index.
    specs = {spec.name: spec for spec in registry.indexes()}
    delivery_date = specs["ix_ont_delivery_deliverydate"]
    assert delivery_date.expressions == ("(properties->>'deliveryDate')",)
    assert "::date" not in delivery_date.ddl()

    status = specs["ix_ont_salesorder_status"]
    assert status.expressions == ("((properties->>'status')::text)",)


def test_index_declarations_are_valid(registry: SchemaRegistry) -> None:
    names = [spec.name for spec in registry.indexes()]
    assert len(names) == len(set(names)), "index names must be unique"
    assert "ix_ont_salesorder_status" in names
    assert "ix_ont_outlet_deliveryweekday" in names


def test_internal_types_marked(registry: SchemaRegistry) -> None:
    assert registry.object_type("ActionProposal").internal is True
    assert registry.object_type("AgentRun").internal is True
    assert registry.object_type("SalesOrder").internal is False
