"""The makgeolli domain runs end to end on the same runtime as the other domains.

Uses its own database so domains never share rows — the same isolation
guarantee the per-instance deployment relies on.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.domains.makgeolli.seed.generator import SeedGenerator
from ontology_runtime.registry import SchemaRegistry
from ontology_runtime.runtime import Runtime

TODAY = dt.date(2026, 10, 25)


@pytest.fixture
def registry() -> SchemaRegistry:
    return SchemaRegistry.from_domain("makgeolli")


@pytest.fixture
def runtime(registry: SchemaRegistry, session: AsyncSession) -> Runtime:
    return Runtime(registry, session)


async def _seeded_session(registry: SchemaRegistry, session: AsyncSession) -> Runtime:
    generator = SeedGenerator(registry, session, seed=42, today=TODAY)
    await generator.reset()
    await generator.run()
    await session.commit()
    return Runtime(registry, session)


# --- seed ---------------------------------------------------------------------


async def test_seed_creates_full_brewery_data(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    generator = SeedGenerator(registry, session, seed=42, today=TODAY)
    await generator.reset()
    summary = await generator.run()
    await session.commit()

    assert summary.products == 10
    assert summary.customers == 5
    assert summary.tanks == 4
    assert summary.materials == 6
    assert summary.batches == 10
    assert summary.orders == 8
    assert summary.shipments == 4
    assert summary.waste_records == 1
    assert summary.temp_readings >= 3

    runtime = Runtime(registry, session)
    for object_type, expected in (
        ("Product", 10),
        ("Customer", 5),
        ("Tank", 4),
        ("RawMaterial", 6),
        ("Batch", 10),
        ("TempReading", summary.temp_readings),
    ):
        page = await runtime.sets.search(object_type, page_size=10)
        assert page.total == expected, object_type


async def test_seed_is_deterministic(registry: SchemaRegistry, session: AsyncSession) -> None:
    counts = []
    for _ in range(2):
        generator = SeedGenerator(registry, session, seed=42, today=TODAY)
        await generator.reset()
        summary = await generator.run()
        await session.commit()
        counts.append(summary.to_dict())
    assert counts[0] == counts[1]


# --- batch lifecycle -----------------------------------------------------------


async def test_create_batch_derives_dates_and_temps(runtime: Runtime) -> None:
    product = await runtime.objects.create(
        "Product",
        {
            "sku": "M9001",
            "name": "테스트 막걸리",
            "category": "생막걸리",
            "alcoholPercent": 6.0,
            "shelfLifeDays": 7,
            "fermentationDays": 5,
            "agingDays": 3,
            "fermentationTempMinC": 10.0,
            "fermentationTempMaxC": 15.0,
            "agingTempMinC": 2.0,
            "agingTempMaxC": 5.0,
            "volumeMl": 900,
            "unitPrice": 3500,
            "active": True,
        },
    )

    result = await runtime.apply(
        "CreateBatch",
        {
            "product": product.rid,
            "brewDate": "2026-10-25",
            "volumeL": 300,
        },
        actor="brewer01",
    )
    assert result.status == "succeeded"

    batches = await runtime.sets.search("Batch", page_size=10)
    batch = batches.objects[0]
    assert batch.properties["fermentationDueOn"] == "2026-10-30"
    assert batch.properties["agingDueOn"] == "2026-11-02"
    assert batch.properties["fermentationTempC"] == 10.0
    assert batch.properties["agingTempC"] == 2.0
    assert batch.properties["status"] == "fermenting"


async def test_batch_lifecycle_sets_expiry_from_shelf_life(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    batch = (
        await runtime.sets.search(
            "Batch", filter={"field": "status", "op": "eq", "value": "aging"}, page_size=1
        )
    ).objects[0]
    product = await runtime.objects.get(str(batch.properties["productRid"]))

    result = await runtime.apply(
        "CompleteAging",
        {"batch": batch.rid, "bottledOn": TODAY.isoformat()},
        actor="brewer01",
    )
    assert result.status == "succeeded"

    refreshed = await runtime.objects.get(batch.rid)
    expected_expiry = TODAY + dt.timedelta(days=int(product.properties["shelfLifeDays"]))
    assert refreshed.properties["status"] == "ready"
    assert refreshed.properties["expiresOn"] == expected_expiry.isoformat()
    assert int(refreshed.properties["bottledQty"]) > 0

    # Bottling creates a warehouse stock row for the batch.
    stocks = await runtime.sets.search(
        "WarehouseStock", filter={"field": "batchRid", "op": "eq", "value": batch.rid}
    )
    assert stocks.total == 1


async def test_cannot_bottle_a_fermenting_batch(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    batch = (
        await runtime.sets.search(
            "Batch", filter={"field": "status", "op": "eq", "value": "fermenting"}, page_size=1
        )
    ).objects[0]
    result = await runtime.apply("CompleteAging", {"batch": batch.rid}, actor="brewer01")
    assert result.status == "failed"


# --- temperature control --------------------------------------------------------


async def test_temp_reading_judges_in_range(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    batch = (
        await runtime.sets.search(
            "Batch", filter={"field": "status", "op": "eq", "value": "fermenting"}, page_size=1
        )
    ).objects[0]

    in_range = await runtime.apply(
        "RecordTempReading",
        {
            "batch": batch.rid,
            "tempC": batch.properties["fermentationTempC"],
            "stage": "fermentation",
        },
        actor="brewer01",
    )
    assert in_range.status == "succeeded"

    readings = await runtime.sets.search(
        "TempReading", filter={"field": "batchRid", "op": "eq", "value": batch.rid}
    )
    latest = max(readings.objects, key=lambda r: r.properties["readingNo"])
    assert latest.properties["inRange"] is True


async def test_temp_reading_detects_deviation(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    batch = (
        await runtime.sets.search(
            "Batch", filter={"field": "status", "op": "eq", "value": "fermenting"}, page_size=1
        )
    ).objects[0]

    result = await runtime.apply(
        "RecordTempReading",
        {
            "batch": batch.rid,
            "tempC": float(batch.properties["fermentationTempC"]) + 8.0,
            "stage": "fermentation",
        },
        actor="brewer01",
    )
    assert result.status == "succeeded"

    readings = await runtime.sets.search(
        "TempReading", filter={"field": "batchRid", "op": "eq", "value": batch.rid}
    )
    latest = max(readings.objects, key=lambda r: r.properties["readingNo"])
    assert latest.properties["inRange"] is False


async def test_temp_reading_rejects_wrong_stage(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    batch = (
        await runtime.sets.search(
            "Batch", filter={"field": "status", "op": "eq", "value": "fermenting"}, page_size=1
        )
    ).objects[0]
    result = await runtime.apply(
        "RecordTempReading",
        {"batch": batch.rid, "tempC": 4.0, "stage": "aging"},
        actor="brewer01",
    )
    assert result.status == "failed"


async def test_temp_deviations_lists_out_of_range(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    batch = (
        await runtime.sets.search(
            "Batch", filter={"field": "status", "op": "eq", "value": "fermenting"}, page_size=1
        )
    ).objects[0]
    await runtime.apply(
        "RecordTempReading",
        {
            "batch": batch.rid,
            "tempC": float(batch.properties["fermentationTempC"]) + 8.0,
            "stage": "fermentation",
        },
        actor="brewer01",
    )

    result = await runtime.run_function("tempDeviations", {"withinDays": 7})
    assert result["count"] >= 1
    row = result["readings"][0]
    assert row["batchNo"] == batch.properties["batchNo"]
    assert row["stage"] == "fermentation"
    # Agents quote these rows to humans: the display name must be resolved.
    assert row["product"] is not None and not row["product"].startswith("ri.")


async def test_adjust_batch_temp_updates_target(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    batch = (
        await runtime.sets.search(
            "Batch", filter={"field": "status", "op": "eq", "value": "fermenting"}, page_size=1
        )
    ).objects[0]
    new_target = float(batch.properties["fermentationTempC"]) + 1.0

    result = await runtime.apply(
        "AdjustBatchTemp",
        {"batch": batch.rid, "stage": "fermentation", "targetTempC": new_target},
        actor="manager01",
    )
    assert result.status == "succeeded"
    refreshed = await runtime.objects.get(batch.rid)
    assert float(refreshed.properties["fermentationTempC"]) == new_target


# --- distribution and stock -----------------------------------------------------


async def test_ship_batch_moves_warehouse_stock(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    batch = (
        await runtime.sets.search(
            "Batch", filter={"field": "status", "op": "eq", "value": "ready"}, page_size=1
        )
    ).objects[0]
    customer = (await runtime.sets.search("Customer", page_size=1)).objects[0]
    stock = (
        await runtime.sets.search(
            "WarehouseStock", filter={"field": "batchRid", "op": "eq", "value": batch.rid}
        )
    ).objects[0]
    before = int(stock.properties["quantity"])

    result = await runtime.apply(
        "ShipBatch",
        {
            "batch": batch.rid,
            "customer": customer.rid,
            "quantity": 5,
            "shipDate": TODAY.isoformat(),
        },
        actor="manager01",
    )
    assert result.status == "succeeded"

    refreshed_stock = await runtime.objects.get(stock.rid)
    assert int(refreshed_stock.properties["quantity"]) == before - 5

    refreshed_batch = await runtime.objects.get(batch.rid)
    assert refreshed_batch.properties["status"] == "ready", "부분 출하에서는 상태가 유지된다"

    shipments = await runtime.sets.search(
        "Shipment", filter={"field": "status", "op": "eq", "value": "in_transit"}
    )
    assert shipments.total >= 1


async def test_ship_batch_rejects_unready_batch(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    batch = (
        await runtime.sets.search(
            "Batch", filter={"field": "status", "op": "eq", "value": "fermenting"}, page_size=1
        )
    ).objects[0]
    customer = (await runtime.sets.search("Customer", page_size=1)).objects[0]
    result = await runtime.apply(
        "ShipBatch", {"batch": batch.rid, "customer": customer.rid}, actor="manager01"
    )
    assert result.status == "failed"


async def test_full_ship_marks_batch_shipped(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    batch = (
        await runtime.sets.search(
            "Batch", filter={"field": "status", "op": "eq", "value": "ready"}, page_size=1
        )
    ).objects[0]
    customer = (await runtime.sets.search("Customer", page_size=1)).objects[0]
    stock = (
        await runtime.sets.search(
            "WarehouseStock", filter={"field": "batchRid", "op": "eq", "value": batch.rid}
        )
    ).objects[0]

    result = await runtime.apply(
        "ShipBatch",
        {
            "batch": batch.rid,
            "customer": customer.rid,
            "quantity": int(stock.properties["quantity"]),
            "shipDate": TODAY.isoformat(),
        },
        actor="manager01",
    )
    assert result.status == "succeeded"
    refreshed = await runtime.objects.get(batch.rid)
    assert refreshed.properties["status"] == "shipped"


async def test_receive_shipment_raises_outlet_stock(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    shipment = (
        await runtime.sets.search(
            "Shipment", filter={"field": "status", "op": "eq", "value": "in_transit"}, page_size=1
        )
    ).objects[0]
    batch = await runtime.objects.get(str(shipment.properties["batchRid"]))

    result = await runtime.apply(
        "ReceiveShipment",
        {"shipment": shipment.rid, "receivedOn": TODAY.isoformat()},
        actor="manager01",
    )
    assert result.status == "succeeded"

    stocks = await runtime.sets.search(
        "OutletStock",
        filter={"field": "customerRid", "op": "eq", "value": shipment.properties["customerRid"]},
    )
    assert any(s.properties["productRid"] == batch.properties["productRid"] for s in stocks.objects)


# --- sales -----------------------------------------------------------------------


async def test_create_sales_order_computes_totals(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    customer = (await runtime.sets.search("Customer", page_size=1)).objects[0]
    products = (await runtime.sets.search("Product", page_size=2)).objects

    lines = [{"productRid": product.rid, "cases": 10} for product in products]
    result = await runtime.apply(
        "CreateSalesOrder",
        {"customer": customer.rid, "orderDate": TODAY.isoformat(), "lines": lines},
        actor="sales01",
    )
    assert result.status == "succeeded"

    expected_total = sum(int(product.properties["unitPrice"]) * 10 for product in products)
    orders = await runtime.sets.search(
        "SalesOrder", filter={"field": "customerRid", "op": "eq", "value": customer.rid}
    )
    new_order = max(orders.objects, key=lambda o: o.properties["orderNo"])
    assert int(new_order.properties["totalAmount"]) == expected_total


async def test_suspended_customer_cannot_order(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    customer = (await runtime.sets.search("Customer", page_size=1)).objects[0]
    await runtime.objects.update(customer.rid, {"status": "suspended"})
    product = (await runtime.sets.search("Product", page_size=1)).objects[0]

    result = await runtime.apply(
        "CreateSalesOrder",
        {
            "customer": customer.rid,
            "orderDate": TODAY.isoformat(),
            "lines": [{"productRid": product.rid, "cases": 3}],
        },
        actor="sales01",
    )
    assert result.status == "failed"


# --- inventory and materials ------------------------------------------------------


async def test_adjust_warehouse_stock_rejects_negative(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    stock = (await runtime.sets.search("WarehouseStock", page_size=1)).objects[0]

    result = await runtime.apply(
        "AdjustWarehouseStock",
        {"stock": stock.rid, "delta": -(int(stock.properties["quantity"]) + 10)},
        actor="manager01",
    )
    assert result.status == "failed", "재고를 음수로 만들 수 없어야 한다"


async def test_restock_material_adds_stock(registry: SchemaRegistry, session: AsyncSession) -> None:
    runtime = await _seeded_session(registry, session)
    material = (await runtime.sets.search("RawMaterial", page_size=1)).objects[0]
    before = float(material.properties["currentStock"])

    result = await runtime.apply(
        "RestockMaterial",
        {"material": material.rid, "amount": 100.0, "restockedOn": TODAY.isoformat()},
        actor="manager01",
    )
    assert result.status == "succeeded"
    refreshed = await runtime.objects.get(material.rid)
    assert float(refreshed.properties["currentStock"]) == before + 100.0


# --- waste -------------------------------------------------------------------------


async def test_partial_waste_keeps_batch_ready(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    batch = (
        await runtime.sets.search(
            "Batch", filter={"field": "status", "op": "eq", "value": "ready"}, page_size=1
        )
    ).objects[0]
    quantity = int(batch.properties["bottledQty"])

    result = await runtime.apply(
        "WasteBatch",
        {"batch": batch.rid, "reason": "damage", "quantity": 2, "wastedOn": TODAY.isoformat()},
        actor="brewer01",
    )
    assert result.status == "succeeded"
    refreshed = await runtime.objects.get(batch.rid)
    assert refreshed.properties["status"] == "ready"
    assert int(refreshed.properties["bottledQty"]) == quantity - 2


async def test_full_waste_marks_batch_wasted(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    batch = (
        await runtime.sets.search(
            "Batch", filter={"field": "status", "op": "eq", "value": "ready"}, page_size=1
        )
    ).objects[0]
    quantity = int(batch.properties["bottledQty"])

    result = await runtime.apply(
        "WasteBatch",
        {"batch": batch.rid, "reason": "expiry", "wastedOn": TODAY.isoformat()},
        actor="brewer01",
    )
    assert result.status == "succeeded"
    refreshed = await runtime.objects.get(batch.rid)
    assert refreshed.properties["status"] == "wasted"
    records = await runtime.sets.search("WasteRecord", page_size=10)
    assert any(r.properties["quantity"] == quantity for r in records.objects)


# --- read functions -----------------------------------------------------------------


async def test_expiring_function_returns_display_names(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    result = await runtime.run_function("expiringBatches", {"withinDays": 30})
    if result["count"] == 0:
        pytest.skip("시드에 임박 배치가 없는 시나리오")
    row = result["batches"][0]
    assert row["product"] is not None and not row["product"].startswith("ri.")
    assert row["productRid"].startswith("ri.makgeolli.object.product.")


async def test_production_pipeline_reports_progress(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    result = await runtime.run_function("productionPipeline", {})
    assert result["count"] >= 1
    assert set(result["byStatus"]) <= {"fermenting", "aging"}
    row = result["batches"][0]
    assert 0 <= row["progressPercent"] <= 100
    assert row["targetTempC"] is not None


async def test_sales_summary_read_function(registry: SchemaRegistry, session: AsyncSession) -> None:
    runtime = await _seeded_session(registry, session)
    result = await runtime.run_function("salesSummary", {"withinDays": 30})
    assert result["totalAmount"] > 0
    assert result["totalCases"] > 0
    assert result["topProducts"][0]["amount"] > 0


async def test_waste_history_read_function(registry: SchemaRegistry, session: AsyncSession) -> None:
    runtime = await _seeded_session(registry, session)
    result = await runtime.run_function("wasteHistory", {})
    assert result["count"] == 1
    assert result["byReason"] == {"expiry": result["totalQuantity"]}
    assert result["records"][0]["reasonName"] == "유통기한"


async def test_reorder_suggestions_cover_active_products(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    result = await runtime.run_function("reorderSuggestions", {})
    assert len(result["suggestions"]) == 10
    for row in result["suggestions"]:
        assert row["leadDays"] >= 0
        assert row["suggestedBottles"] >= 0


async def test_makgeolli_rejects_other_domain_objects(runtime: Runtime) -> None:
    from ontology_runtime.errors import ObjectTypeNotFound

    with pytest.raises(ObjectTypeNotFound):
        await runtime.sets.search("Outlet")
    with pytest.raises(ObjectTypeNotFound):
        await runtime.sets.search("Store")
