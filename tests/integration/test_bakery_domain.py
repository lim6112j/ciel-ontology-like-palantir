"""The bakery domain runs end to end on the same runtime as liquor.

Uses its own database so the two domains never share rows — the same isolation
guarantee the per-instance deployment relies on.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.domains.bakery.seed.generator import SeedGenerator
from ontology_runtime.registry import SchemaRegistry
from ontology_runtime.runtime import Runtime

TODAY = dt.date(2026, 10, 25)


@pytest.fixture
def registry() -> SchemaRegistry:
    return SchemaRegistry.from_domain("bakery")


@pytest.fixture
def runtime(registry: SchemaRegistry, session: AsyncSession) -> Runtime:
    return Runtime(registry, session)


async def test_seed_creates_batches_and_links(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    generator = SeedGenerator(registry, session, seed=42, today=TODAY)
    await generator.reset()
    summary = await generator.run()
    await session.commit()

    assert summary.products == 5
    assert summary.stores == 4
    assert summary.batches == 6
    assert summary.plans == 3
    assert summary.shipments == 2
    assert summary.waste_records == 1
    assert summary.stocks > 0

    runtime = Runtime(registry, session)
    for object_type, expected in (
        ("Batch", 6),
        ("ProductionPlan", 3),
        ("Shipment", 2),
        ("WasteRecord", 1),
    ):
        page = await runtime.sets.search(object_type, page_size=10)
        assert page.total == expected, object_type


async def test_record_batch_action_computes_expiry(runtime: Runtime) -> None:
    product = await runtime.objects.create(
        "Product",
        {
            "sku": "B0001",
            "name": "우유식빵",
            "category": "식빵",
            "shelfLifeDays": 5,
            "unitPrice": 3500,
            "active": True,
        },
    )
    produced_on = "2026-10-25"

    result = await runtime.apply(
        "RecordBatch",
        {"product": product.rid, "quantity": 12, "producedOn": produced_on},
        actor="tester",
    )
    assert result.status == "succeeded"

    batches = await runtime.sets.search("Batch", page_size=10)
    batch = batches.objects[0]
    assert batch.properties["expiresOn"] == "2026-10-30"
    assert batch.properties["quantity"] == 12
    assert batch.properties["status"] == "planned"


async def test_expiring_function_returns_only_live_batches(runtime: Runtime) -> None:
    product = await runtime.objects.create(
        "Product",
        {
            "sku": "B0002",
            "name": "크루아상",
            "category": "페이스트리",
            "shelfLifeDays": 2,
            "unitPrice": 2800,
            "active": True,
        },
    )
    today = dt.date.today()
    await runtime.apply(
        "RecordBatch",
        {"product": product.rid, "quantity": 6, "producedOn": today.isoformat()},
        actor="tester",
    )

    result = await runtime.run_function("expiringBatches", {"withinDays": 3})
    assert result["count"] == 1
    row = result["batches"][0]
    assert row["quantity"] == 6
    # Agents quote these rows to humans: the display name must be resolved,
    # not left as a rid the agent cannot confidently translate.
    assert row["product"] == "크루아상"
    assert row["productRid"].startswith("ri.bakery.object.product.")


async def test_bakery_rejects_liquor_object_types(runtime: Runtime) -> None:
    from ontology_runtime.errors import ObjectTypeNotFound

    with pytest.raises(ObjectTypeNotFound):
        await runtime.sets.search("SalesOrder")


# --- production planning -----------------------------------------------------


async def _seeded_session(registry: SchemaRegistry, session: AsyncSession) -> Runtime:
    generator = SeedGenerator(registry, session, seed=42, today=TODAY)
    await generator.reset()
    await generator.run()
    await session.commit()
    return Runtime(registry, session)


async def test_upsert_product_creates_then_updates(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    result = await runtime.apply(
        "UpsertProduct",
        {
            "sku": "B9001",
            "name": "치아바타",
            "category": "식빵",
            "shelfLifeDays": 3,
            "unitPrice": 4000,
        },
        actor="manager01",
    )
    assert result.status == "succeeded"
    page = await runtime.sets.search(
        "Product", filter={"field": "sku", "op": "eq", "value": "B9001"}
    )
    assert page.total == 1

    await runtime.apply(
        "UpsertProduct",
        {
            "sku": "B9001",
            "name": "치아바타",
            "category": "식빵",
            "shelfLifeDays": 3,
            "unitPrice": 4500,
        },
        actor="manager01",
    )
    page = await runtime.sets.search(
        "Product", filter={"field": "sku", "op": "eq", "value": "B9001"}
    )
    assert page.total == 1
    assert page.objects[0].properties["unitPrice"] == 4500


async def test_plan_start_complete_creates_baked_batch(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    product = (await runtime.sets.search("Product", page_size=1)).objects[0]

    result = await runtime.apply(
        "CreateProductionPlan",
        {"product": product.rid, "planDate": TODAY.isoformat(), "plannedQty": 15},
        actor="baker01",
    )
    assert result.status == "succeeded"
    plans = await runtime.sets.search(
        "ProductionPlan",
        filter={
            "and": [
                {"field": "status", "op": "eq", "value": "planned"},
                {"field": "plannedQty", "op": "eq", "value": 15},
            ]
        },
        page_size=10,
    )
    plan = plans.objects[0]

    started = await runtime.apply("StartProductionPlan", {"plan": plan.rid}, actor="baker01")
    assert started.status == "succeeded"

    completed = await runtime.apply(
        "CompleteProductionPlan", {"plan": plan.rid, "producedQty": 14}, actor="baker01"
    )
    assert completed.status == "succeeded"
    batch_page = await runtime.sets.search(
        "Batch", filter={"field": "status", "op": "eq", "value": "baked"}, page_size=10
    )
    quantities = {b.properties["quantity"] for b in batch_page.objects}
    assert 14 in quantities
    refreshed = await runtime.objects.get(plan.rid)
    assert refreshed.properties["status"] == "completed"
    assert refreshed.properties["producedQty"] == 14


async def test_complete_requires_in_progress_plan(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    plans = await runtime.sets.search(
        "ProductionPlan", filter={"field": "status", "op": "eq", "value": "planned"}, page_size=10
    )
    result = await runtime.apply(
        "CompleteProductionPlan", {"plan": plans.objects[0].rid}, actor="baker01"
    )
    assert result.status == "failed"


async def test_inactive_product_cannot_be_planned(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    product = (await runtime.sets.search("Product", page_size=1)).objects[0]
    await runtime.objects.update(product.rid, {"active": False})

    result = await runtime.apply(
        "CreateProductionPlan",
        {"product": product.rid, "planDate": TODAY.isoformat(), "plannedQty": 5},
        actor="baker01",
    )
    assert result.status == "failed"


# --- shipments and stock -----------------------------------------------------


async def test_ship_batch_moves_stock_and_completes_batch(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    batch = (
        await runtime.sets.search(
            "Batch", filter={"field": "status", "op": "eq", "value": "baked"}, page_size=10
        )
    ).objects[0]
    store = (await runtime.sets.search("Store", page_size=1)).objects[0]

    result = await runtime.apply(
        "ShipBatch",
        {
            "batch": batch.rid,
            "store": store.rid,
            "shipDate": TODAY.isoformat(),
        },
        actor="manager01",
    )
    assert result.status == "succeeded"

    shipped = await runtime.objects.get(batch.rid)
    assert shipped.properties["status"] == "shipped"

    stocks = await runtime.sets.search(
        "StoreStock", filter={"field": "storeRid", "op": "eq", "value": store.rid}, page_size=10
    )
    totals = {s.properties["productRid"]: s.properties["quantity"] for s in stocks.objects}
    assert totals[shipped.properties["productRid"]] >= int(batch.properties["quantity"])

    shipments = await runtime.sets.search(
        "Shipment", filter={"field": "status", "op": "eq", "value": "in_transit"}, page_size=10
    )
    assert shipments.total >= 1


async def test_receive_shipment_requires_in_transit(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    delivered = (
        await runtime.sets.search(
            "Shipment", filter={"field": "status", "op": "eq", "value": "delivered"}, page_size=1
        )
    ).objects[0]

    result = await runtime.apply(
        "ReceiveShipment",
        {"shipment": delivered.rid, "receivedOn": TODAY.isoformat()},
        actor="manager01",
    )
    assert result.status == "failed"


async def test_planned_batch_cannot_ship(registry: SchemaRegistry, session: AsyncSession) -> None:
    runtime = await _seeded_session(registry, session)
    batch = (
        await runtime.sets.search(
            "Batch", filter={"field": "status", "op": "eq", "value": "planned"}, page_size=1
        )
    ).objects[0]
    store = (await runtime.sets.search("Store", page_size=1)).objects[0]

    result = await runtime.apply(
        "ShipBatch", {"batch": batch.rid, "store": store.rid}, actor="manager01"
    )
    assert result.status == "failed"


# --- waste and stock adjustment ----------------------------------------------


async def test_full_waste_marks_batch_wasted(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    batch = (
        await runtime.sets.search(
            "Batch", filter={"field": "status", "op": "eq", "value": "planned"}, page_size=10
        )
    ).objects[0]
    quantity = int(batch.properties["quantity"])

    result = await runtime.apply(
        "WasteBatch",
        {"batch": batch.rid, "reason": "quality", "wastedOn": TODAY.isoformat()},
        actor="baker01",
    )
    assert result.status == "succeeded"
    refreshed = await runtime.objects.get(batch.rid)
    assert refreshed.properties["status"] == "wasted"
    records = await runtime.sets.search("WasteRecord", page_size=10)
    assert any(r.properties["quantity"] == quantity for r in records.objects)


async def test_partial_waste_keeps_batch_alive(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    batch = (
        await runtime.sets.search(
            "Batch", filter={"field": "status", "op": "eq", "value": "planned"}, page_size=10
        )
    ).objects[0]

    result = await runtime.apply(
        "WasteBatch",
        {"batch": batch.rid, "reason": "damage", "quantity": 2, "wastedOn": TODAY.isoformat()},
        actor="baker01",
    )
    assert result.status == "succeeded"
    refreshed = await runtime.objects.get(batch.rid)
    assert refreshed.properties["status"] == "planned"
    assert refreshed.properties["quantity"] == int(batch.properties["quantity"]) - 2


async def test_adjust_store_stock_creates_and_updates(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    store = (await runtime.sets.search("Store", page_size=1)).objects[0]
    product = (await runtime.sets.search("Product", page_size=1)).objects[0]

    stocks = await runtime.sets.search(
        "StoreStock", filter={"field": "storeRid", "op": "eq", "value": store.rid}, page_size=10
    )
    initial = next(
        (
            int(s.properties["quantity"])
            for s in stocks.objects
            if s.properties["productRid"] == product.rid
        ),
        0,
    )

    result = await runtime.apply(
        "AdjustStoreStock",
        {"store": store.rid, "product": product.rid, "delta": 7},
        actor="manager01",
    )
    assert result.status == "succeeded"
    stocks = await runtime.sets.search(
        "StoreStock", filter={"field": "storeRid", "op": "eq", "value": store.rid}, page_size=10
    )
    assert any(
        s.properties["productRid"] == product.rid and s.properties["quantity"] == initial + 7
        for s in stocks.objects
    )

    result = await runtime.apply(
        "AdjustStoreStock",
        {"store": store.rid, "product": product.rid, "delta": -(initial + 10)},
        actor="manager01",
    )
    assert result.status == "failed", "재고를 음수로 만들 수 없어야 한다"


# --- read functions -----------------------------------------------------------


async def test_store_stock_read_function(registry: SchemaRegistry, session: AsyncSession) -> None:
    runtime = await _seeded_session(registry, session)
    store = (await runtime.sets.search("Store", page_size=1)).objects[0]

    result = await runtime.run_function("storeStock", {"store": store.rid})
    assert result["count"] >= 1
    assert result["total"] > 0
    assert result["stocks"][0]["product"] is not None


async def test_production_summary_read_function(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)

    result = await runtime.run_function("productionSummary", {"planDate": TODAY.isoformat()})
    assert result["count"] == 2
    assert result["byStatus"].get("planned") == 1
    assert result["byStatus"].get("in_progress") == 1


async def test_waste_history_read_function(registry: SchemaRegistry, session: AsyncSession) -> None:
    runtime = await _seeded_session(registry, session)

    # Seed wastes the first planned batch (B-00002, 통밀식빵) for expiry.
    result = await runtime.run_function("wasteHistory", {})
    assert result["count"] == 1
    assert result["totalQuantity"] == 25
    assert result["byReason"] == {"expiry": 25}
    assert result["records"][0]["batchNo"] == "B-00002"

    # Filtering by a product with no waste returns an empty, well-formed result.
    product = (
        await runtime.sets.search(
            "Product", filter={"field": "sku", "op": "eq", "value": "B0004"}, page_size=1
        )
    ).objects[0]
    empty = await runtime.run_function("wasteHistory", {"product": product.rid})
    assert empty["count"] == 0
    assert empty["records"] == []
