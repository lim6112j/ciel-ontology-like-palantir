"""Link store integration tests: cardinality, traversal in both directions."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.errors import ConflictError, NotFoundError
from ontology_runtime.registry import SchemaRegistry
from ontology_runtime.store.link_store import LinkStore
from ontology_runtime.store.object_store import ObjectStore


@pytest.fixture
def stores(demo_registry: SchemaRegistry, session: AsyncSession) -> tuple[ObjectStore, LinkStore]:
    return ObjectStore(demo_registry, session), LinkStore(demo_registry, session)


async def _outlet(objects: ObjectStore, name: str):
    return await objects.create(
        "Outlet", {"name": name, "outletType": "음식점", "status": "active"}
    )


async def _order(objects: ObjectStore, order_no: str):
    return await objects.create("Order", {"orderNo": order_no, "status": "draft"})


async def test_create_and_traverse_forward(stores, demo_registry: SchemaRegistry) -> None:
    objects, links = stores
    outlet = await _outlet(objects, "A")
    order = await _order(objects, "SO-1")
    await links.create("orders", outlet.rid, order.rid)

    view = demo_registry.link_on("Outlet", "orders")
    assert [o.rid for o in await links.targets(view, outlet.rid)] == [order.rid]


async def test_inverse_link_is_derived(stores, demo_registry: SchemaRegistry) -> None:
    objects, links = stores
    outlet = await _outlet(objects, "A")
    order = await _order(objects, "SO-1")
    await links.create("orders", outlet.rid, order.rid)

    inverse = demo_registry.link_on("Order", "outlet")
    assert inverse.is_forward is False
    assert [o.rid for o in await links.targets(inverse, order.rid)] == [outlet.rid]


async def test_duplicate_link_is_idempotent(stores) -> None:
    objects, links = stores
    outlet = await _outlet(objects, "A")
    order = await _order(objects, "SO-1")
    await links.create("orders", outlet.rid, order.rid)
    await links.create("orders", outlet.rid, order.rid)
    view = objects.registry.link_on("Outlet", "orders")
    assert await links.count(view, outlet.rid) == 1


async def test_one_to_many_allows_many_targets_per_source(stores) -> None:
    objects, links = stores
    outlet = await _outlet(objects, "A")
    first = await _order(objects, "SO-1")
    second = await _order(objects, "SO-2")
    # fromCardinality=many: one outlet may link to several orders.
    await links.create("orders", outlet.rid, first.rid)
    await links.create("orders", outlet.rid, second.rid)
    view = objects.registry.link_on("Outlet", "orders")
    assert await links.count(view, outlet.rid) == 2


async def test_one_source_per_target_enforced(stores) -> None:
    objects, links = stores
    first_outlet = await _outlet(objects, "A")
    second_outlet = await _outlet(objects, "B")
    order = await _order(objects, "SO-1")
    await links.create("orders", first_outlet.rid, order.rid)
    # toCardinality=one: an order belongs to exactly one outlet.
    with pytest.raises(ConflictError, match="one source per target"):
        await links.create("orders", second_outlet.rid, order.rid)


async def test_wrong_object_type_rejected(stores) -> None:
    objects, links = stores
    outlet = await _outlet(objects, "A")
    other = await _outlet(objects, "B")
    with pytest.raises(ConflictError, match="expects toObjectType 'Order'"):
        await links.create("orders", outlet.rid, other.rid)


async def test_missing_object_rejected(stores) -> None:
    objects, links = stores
    outlet = await _outlet(objects, "A")
    with pytest.raises(NotFoundError):
        await links.create("orders", outlet.rid, "ri.liquor.object.order.missing")


async def test_delete_link(stores, demo_registry: SchemaRegistry) -> None:
    objects, links = stores
    outlet = await _outlet(objects, "A")
    order = await _order(objects, "SO-1")
    await links.create("orders", outlet.rid, order.rid)
    await links.delete("orders", outlet.rid, order.rid)
    view = demo_registry.link_on("Outlet", "orders")
    assert await links.count(view, outlet.rid) == 0


async def test_targets_exclude_soft_deleted(stores, demo_registry: SchemaRegistry) -> None:
    objects, links = stores
    outlet = await _outlet(objects, "A")
    order = await _order(objects, "SO-1")
    await links.create("orders", outlet.rid, order.rid)
    await objects.soft_delete(order.rid)
    view = demo_registry.link_on("Outlet", "orders")
    assert await links.targets(view, outlet.rid) == []
