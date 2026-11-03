"""The makgeolli domain runs end to end on the same runtime as the other domains.

Uses its own database so domains never share rows — the same isolation
guarantee the per-instance deployment relies on.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.domains.makgeolli.seed.generator import SeedGenerator
from ontology_runtime.errors import ConflictError
from ontology_runtime.registry import SchemaRegistry
from ontology_runtime.runtime import Runtime
from ontology_runtime.store.link_store import LinkStore

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
    assert summary.teams == 6
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
        ("Team", 6),
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


# --- teams ---------------------------------------------------------------------


async def test_seed_assigns_every_object_to_a_team(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    links = LinkStore(registry, session)
    teams = {team.properties["kind"]: team for team in (await runtime.sets.search("Team")).objects}
    assert set(teams) == {"양조", "품질", "포장", "물류", "영업", "자재"}

    for object_type, kind in (
        ("Batch", "양조"),
        ("Tank", "양조"),
        ("TempReading", "품질"),
        ("WasteRecord", "품질"),
        ("WarehouseStock", "포장"),
        ("Shipment", "물류"),
        ("SalesOrder", "영업"),
        ("Customer", "영업"),
        ("RawMaterial", "자재"),
    ):
        objects = (await runtime.sets.search(object_type, page_size=50)).objects
        assert objects, object_type
        team = teams[kind]
        for obj in objects:
            assert obj.properties["teamRid"] == team.rid, object_type
        view = next(v for v in registry.links_of("Team") if v.target_type == object_type)
        assert len(await links.targets(view, team.rid)) == len(objects), object_type


async def test_an_object_answers_to_exactly_one_team(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    links = LinkStore(registry, session)
    batch = (await runtime.sets.search("Batch", page_size=1)).objects[0]
    teams = (await runtime.sets.search("Team")).objects
    brewing = next(team for team in teams if team.properties["kind"] == "양조")
    quality = next(team for team in teams if team.properties["kind"] == "품질")

    with pytest.raises(ConflictError):
        await links.create("teamBatches", quality.rid, batch.rid)

    view = registry.link_on("Team", "batches")
    assert batch.rid in [obj.rid for obj in await links.targets(view, brewing.rid)]


async def test_upsert_team_creates_then_updates(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    result = await runtime.apply(
        "UpsertTeam",
        {"teamNo": "T90", "name": "연구개발팀", "kind": "품질", "since": "2026-01-05"},
        actor="manager01",
    )
    assert result.status == "succeeded"

    created = await runtime.sets.search(
        "Team", filter={"field": "teamNo", "op": "eq", "value": "T90"}
    )
    assert created.total == 1
    assert created.objects[0].properties["kind"] == "품질"
    assert created.objects[0].properties["since"] == "2026-01-05"

    result = await runtime.apply(
        "UpsertTeam",
        {"teamNo": "T90", "name": "품질연구팀", "kind": "품질"},
        actor="manager01",
    )
    assert result.status == "succeeded"

    updated = await runtime.sets.search(
        "Team", filter={"field": "teamNo", "op": "eq", "value": "T90"}
    )
    assert updated.total == 1, "팀번호는 유지하고 정보만 갱신한다"
    assert updated.objects[0].properties["name"] == "품질연구팀"


# --- write path -----------------------------------------------------------------


async def test_write_path_links_new_objects_to_their_team(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    """Everything the single write path creates carries its owning team."""
    runtime = await _seeded_session(registry, session)
    links = LinkStore(registry, session)
    teams = {team.properties["kind"]: team for team in (await runtime.sets.search("Team")).objects}
    product = (await runtime.sets.search("Product", page_size=1)).objects[0]
    customer = (await runtime.sets.search("Customer", page_size=1)).objects[0]

    batch_run = await runtime.apply(
        "CreateBatch",
        {"product": product.rid, "brewDate": TODAY.isoformat(), "volumeL": 300},
        actor="brewer01",
    )
    assert batch_run.status == "succeeded"
    batch = (
        await runtime.sets.search(
            "Batch", filter={"field": "batchNo", "op": "eq", "value": "BATCH-00011"}
        )
    ).objects[0]
    assert batch.properties["teamRid"] == teams["양조"].rid
    view = registry.link_on("Team", "batches")
    assert batch.rid in [obj.rid for obj in await links.targets(view, teams["양조"].rid)]

    reading_run = await runtime.apply(
        "RecordTempReading",
        {"batch": batch.rid, "tempC": 12.0, "stage": "fermentation"},
        actor="brewer01",
    )
    assert reading_run.status == "succeeded"
    reading = (
        await runtime.sets.search(
            "TempReading", filter={"field": "batchRid", "op": "eq", "value": batch.rid}
        )
    ).objects[0]
    assert reading.properties["teamRid"] == teams["품질"].rid

    order_run = await runtime.apply(
        "CreateSalesOrder",
        {
            "customer": customer.rid,
            "orderDate": TODAY.isoformat(),
            "lines": [{"productRid": product.rid, "cases": 6}],
        },
        actor="sales01",
    )
    assert order_run.status == "succeeded"
    order = (
        await runtime.sets.search(
            "SalesOrder", filter={"field": "status", "op": "eq", "value": "draft"}
        )
    ).objects[0]
    assert order.properties["teamRid"] == teams["영업"].rid


async def test_write_path_links_bottling_and_shipping_to_their_team(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    """Bottling hands stock to packaging; shipping hands it to logistics."""
    runtime = await _seeded_session(registry, session)
    teams = {team.properties["kind"]: team for team in (await runtime.sets.search("Team")).objects}
    customer = (await runtime.sets.search("Customer", page_size=1)).objects[0]

    aging = (
        await runtime.sets.search(
            "Batch", filter={"field": "status", "op": "eq", "value": "aging"}, page_size=1
        )
    ).objects[0]
    result = await runtime.apply("CompleteAging", {"batch": aging.rid}, actor="brewer01")
    assert result.status == "succeeded"
    stock = (
        await runtime.sets.search(
            "WarehouseStock", filter={"field": "batchRid", "op": "eq", "value": aging.rid}
        )
    ).objects[0]
    assert stock.properties["teamRid"] == teams["포장"].rid

    ready = (
        await runtime.sets.search(
            "Batch", filter={"field": "status", "op": "eq", "value": "ready"}, page_size=1
        )
    ).objects[0]
    result = await runtime.apply(
        "ShipBatch",
        {
            "batch": ready.rid,
            "customer": customer.rid,
            "quantity": 5,
            "shipDate": TODAY.isoformat(),
        },
        actor="manager01",
    )
    assert result.status == "succeeded"
    shipments = (
        await runtime.sets.search(
            "Shipment", filter={"field": "batchRid", "op": "eq", "value": ready.rid}
        )
    ).objects
    assert shipments, "출하가 생성되어야 한다"
    for shipment in shipments:
        assert shipment.properties["teamRid"] == teams["물류"].rid


async def test_upsert_team_rejects_unknown_kind(
    registry: SchemaRegistry, session: AsyncSession
) -> None:
    runtime = await _seeded_session(registry, session)
    result = await runtime.apply(
        "UpsertTeam",
        {"teamNo": "T91", "name": "알수없는팀", "kind": "마케팅"},
        actor="manager01",
    )
    assert result.status == "failed"

    remaining = await runtime.sets.search(
        "Team", filter={"field": "teamNo", "op": "eq", "value": "T91"}
    )
    assert remaining.total == 0


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
