"""Write functions not covered by the lifecycle tests: analytics, master data, ops."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.config import SCHEMA_DIR
from ontology_runtime.functions.write.proposals import apply_approved_proposal
from ontology_runtime.registry import SchemaRegistry
from ontology_runtime.runtime import Runtime


@pytest.fixture
def runtime(session: AsyncSession) -> Runtime:
    return Runtime(SchemaRegistry.from_directory(SCHEMA_DIR), session)


async def _world(runtime: Runtime) -> dict[str, str]:
    depot = await runtime.objects.create(
        "Depot",
        {"depotNo": "D1", "name": "창고", "region": "수도권", "lat": 37.5, "lon": 127.0},
    )
    rep = await runtime.objects.create(
        "SalesRep",
        {"employeeNo": "R1", "name": "김영업", "status": "active", "depotRid": depot.rid},
    )
    product = await runtime.objects.create(
        "Product",
        {
            "sku": "P1",
            "name": "소주",
            "category": "소주",
            "manufacturer": "제조사",
            "volumeMl": 360,
            "unitsPerCase": 30,
            "unitPrice": 1200,
            "casePrice": 36000,
            "taxType": "과세",
            "active": True,
        },
    )
    outlet = await runtime.objects.create(
        "Outlet",
        {
            "outletNo": "O1",
            "name": "행복식당",
            "outletType": "일반음식점",
            "status": "active",
            "deliveryWeekday": 1,
            "lat": 37.52,
            "lon": 127.03,
            "depotRid": depot.rid,
            "salesRepRid": rep.rid,
        },
    )
    driver = await runtime.objects.create(
        "Driver",
        {
            "employeeNo": "DR1",
            "name": "박기사",
            "employmentType": "직영",
            "licenseType": "1종보통",
            "status": "available",
            "depotRid": depot.rid,
        },
    )
    vehicle = await runtime.objects.create(
        "Vehicle",
        {
            "plateNo": "12가3456",
            "vehicleType": "1톤탑차",
            "capacityCases": 100,
            "capacityWeightKg": 1000,
            "status": "available",
            "depotRid": depot.rid,
        },
    )
    return {
        "depot": depot.rid,
        "rep": rep.rid,
        "product": product.rid,
        "outlet": outlet.rid,
        "driver": driver.rid,
        "vehicle": vehicle.rid,
    }


class TestOrderLineFunctions:
    async def test_add_order_line_recalculates_totals(self, runtime: Runtime) -> None:
        ids = await _world(runtime)
        created = await runtime.apply(
            "CreateSalesOrder",
            {
                "outlet": ids["outlet"],
                "orderDate": "2026-10-26",
                "lines": [{"productRid": ids["product"], "cases": 2}],
            },
        )
        order_rid = created.data["created"]["SalesOrder"][0]
        before = await runtime.objects.get(order_rid)
        assert before.properties["totalAmount"] == 72000

        added = await runtime.apply(
            "AddOrderLine", {"order": order_rid, "product": ids["product"], "cases": 3}
        )
        assert added.status == "succeeded", added.violations
        after = await runtime.objects.get(order_rid)
        assert after.properties["totalAmount"] == 180000
        assert after.properties["totalCases"] == 5

    async def test_remove_order_line_recalculates_totals(self, runtime: Runtime) -> None:
        ids = await _world(runtime)
        created = await runtime.apply(
            "CreateSalesOrder",
            {
                "outlet": ids["outlet"],
                "orderDate": "2026-10-26",
                "lines": [{"productRid": ids["product"], "cases": 2}],
            },
        )
        order_rid = created.data["created"]["SalesOrder"][0]
        lines = await runtime.links.targets(
            runtime.registry.link_on("SalesOrder", "lines"), order_rid
        )

        removed = await runtime.apply("RemoveOrderLine", {"line": lines[0].rid})
        assert removed.status == "succeeded", removed.violations
        after = await runtime.objects.get(order_rid)
        assert after.properties["totalAmount"] == 0
        assert after.properties["totalCases"] == 0

    async def test_add_line_rejected_after_submission(self, runtime: Runtime) -> None:
        ids = await _world(runtime)
        created = await runtime.apply(
            "CreateSalesOrder",
            {
                "outlet": ids["outlet"],
                "orderDate": "2026-10-26",
                "lines": [{"productRid": ids["product"], "cases": 2}],
            },
        )
        order_rid = created.data["created"]["SalesOrder"][0]
        await runtime.apply("SubmitSalesOrder", {"order": order_rid})
        result = await runtime.apply(
            "AddOrderLine", {"order": order_rid, "product": ids["product"], "cases": 1}
        )
        assert result.status == "failed"


class TestDeliveryOps:
    async def test_complete_delivery_marks_partial_when_stop_failed(self, runtime: Runtime) -> None:
        ids = await _world(runtime)
        delivery = await runtime.objects.create(
            "Delivery",
            {
                "deliveryNo": "DL-1",
                "deliveryDate": dt.date.today().isoformat(),
                "depotRid": ids["depot"],
                "driverRid": ids["driver"],
                "status": "in_progress",
            },
        )
        await runtime.objects.create(
            "DeliveryStop",
            {
                "stopNo": "DL-1-01",
                "sequence": 1,
                "status": "completed",
                "outletRid": ids["outlet"],
                "deliveryRid": delivery.rid,
            },
        )
        await runtime.objects.create(
            "DeliveryStop",
            {
                "stopNo": "DL-1-02",
                "sequence": 2,
                "status": "failed",
                "outletRid": ids["outlet"],
                "deliveryRid": delivery.rid,
            },
        )

        result = await runtime.apply("CompleteDelivery", {"delivery": delivery.rid})
        assert result.status == "succeeded", result.violations
        updated = await runtime.objects.get(delivery.rid)
        assert updated.properties["status"] == "partially_completed"

    async def test_complete_delivery_rejects_open_stops(self, runtime: Runtime) -> None:
        ids = await _world(runtime)
        delivery = await runtime.objects.create(
            "Delivery",
            {
                "deliveryNo": "DL-2",
                "deliveryDate": dt.date.today().isoformat(),
                "depotRid": ids["depot"],
                "status": "in_progress",
            },
        )
        await runtime.objects.create(
            "DeliveryStop",
            {
                "stopNo": "DL-2-01",
                "sequence": 1,
                "status": "planned",
                "outletRid": ids["outlet"],
                "deliveryRid": delivery.rid,
            },
        )
        result = await runtime.apply("CompleteDelivery", {"delivery": delivery.rid})
        assert result.status == "failed"
        assert "정류장" in result.violations[0]["message"]

    async def test_reassign_driver(self, runtime: Runtime) -> None:
        ids = await _world(runtime)
        replacement = await runtime.objects.create(
            "Driver",
            {
                "employeeNo": "DR2",
                "name": "이기사",
                "employmentType": "직영",
                "licenseType": "1종대형",
                "status": "available",
                "depotRid": ids["depot"],
            },
        )
        delivery = await runtime.objects.create(
            "Delivery",
            {
                "deliveryNo": "DL-3",
                "deliveryDate": dt.date.today().isoformat(),
                "depotRid": ids["depot"],
                "driverRid": ids["driver"],
                "status": "planned",
            },
        )
        result = await runtime.apply(
            "ReassignDriver", {"delivery": delivery.rid, "driver": replacement.rid}
        )
        assert result.status == "succeeded", result.violations
        updated = await runtime.objects.get(delivery.rid)
        assert updated.properties["driverRid"] == replacement.rid

    async def test_reassign_driver_rejects_unavailable(self, runtime: Runtime) -> None:
        ids = await _world(runtime)
        busy = await runtime.objects.create(
            "Driver",
            {
                "employeeNo": "DR3",
                "name": "최기사",
                "employmentType": "직영",
                "licenseType": "1종보통",
                "status": "on_leave",
                "depotRid": ids["depot"],
            },
        )
        delivery = await runtime.objects.create(
            "Delivery",
            {
                "deliveryNo": "DL-4",
                "deliveryDate": dt.date.today().isoformat(),
                "depotRid": ids["depot"],
                "status": "planned",
            },
        )
        result = await runtime.apply(
            "ReassignDriver", {"delivery": delivery.rid, "driver": busy.rid}
        )
        assert result.status == "failed"

    async def test_reassign_stop_moves_to_other_delivery(self, runtime: Runtime) -> None:
        ids = await _world(runtime)
        source = await runtime.objects.create(
            "Delivery",
            {
                "deliveryNo": "DL-5",
                "deliveryDate": dt.date.today().isoformat(),
                "depotRid": ids["depot"],
                "status": "planned",
            },
        )
        target = await runtime.objects.create(
            "Delivery",
            {
                "deliveryNo": "DL-6",
                "deliveryDate": dt.date.today().isoformat(),
                "depotRid": ids["depot"],
                "status": "planned",
            },
        )
        stop = await runtime.objects.create(
            "DeliveryStop",
            {
                "stopNo": "DL-5-01",
                "sequence": 1,
                "status": "failed",
                "outletRid": ids["outlet"],
                "deliveryRid": source.rid,
            },
        )
        result = await runtime.apply(
            "ReassignStop", {"stop": stop.rid, "targetDelivery": target.rid}
        )
        assert result.status == "succeeded", result.violations
        updated = await runtime.objects.get(stop.rid)
        assert updated.properties["deliveryRid"] == target.rid
        assert updated.properties["status"] == "planned"


class TestMasterData:
    async def test_upsert_outlet_creates_then_updates(self, runtime: Runtime) -> None:
        ids = await _world(runtime)
        created = await runtime.apply(
            "UpsertOutlet",
            {
                "name": "새거래처",
                "outletType": "소매점",
                "address": "서울",
                "deliveryWeekday": 3,
                "depot": ids["depot"],
            },
        )
        assert created.status == "succeeded", created.violations
        outlets = await runtime.search(
            "Outlet", filter={"field": "name", "op": "eq", "value": "새거래처"}
        )
        assert outlets.total == 1
        new_rid = outlets.objects[0].rid

        updated = await runtime.apply(
            "UpsertOutlet",
            {
                "outletNo": outlets.objects[0].properties["outletNo"],
                "name": "새거래처2",
                "outletType": "마트",
            },
        )
        assert updated.status == "succeeded", updated.violations
        assert (await runtime.objects.get(new_rid)).properties["name"] == "새거래처2"

    async def test_upsert_delivery_route(self, runtime: Runtime) -> None:
        ids = await _world(runtime)
        first = await runtime.apply(
            "UpsertDeliveryRoute",
            {
                "routeCode": "RT-1",
                "name": "월요노선",
                "weekday": 0,
                "depot": ids["depot"],
                "salesRep": ids["rep"],
            },
        )
        assert first.status == "succeeded", first.violations
        routes = await runtime.search("DeliveryRoute", page_size=10)
        assert routes.total == 1

        second = await runtime.apply(
            "UpsertDeliveryRoute",
            {
                "routeCode": "RT-1",
                "name": "월요노선-수정",
                "weekday": 0,
                "depot": ids["depot"],
            },
        )
        assert second.status == "succeeded", second.violations
        routes = await runtime.search("DeliveryRoute", page_size=10)
        assert routes.total == 1
        assert routes.objects[0].properties["name"] == "월요노선-수정"


class TestAnalytics:
    async def test_driver_performance(self, runtime: Runtime) -> None:
        ids = await _world(runtime)
        delivery = await runtime.objects.create(
            "Delivery",
            {
                "deliveryNo": "DL-7",
                "deliveryDate": dt.date.today().isoformat(),
                "depotRid": ids["depot"],
                "driverRid": ids["driver"],
                "status": "completed",
            },
        )
        planned = dt.datetime.now(dt.UTC)
        await runtime.objects.create(
            "DeliveryStop",
            {
                "stopNo": "DL-7-01",
                "sequence": 1,
                "status": "completed",
                "plannedAt": planned.isoformat(),
                "completedAt": (planned + dt.timedelta(minutes=10)).isoformat(),
                "actualCases": 5,
                "outletRid": ids["outlet"],
                "deliveryRid": delivery.rid,
            },
        )
        result = await runtime.run_function(
            "driverPerformance",
            {"from": dt.date.today().isoformat(), "to": dt.date.today().isoformat()},
        )
        assert len(result["drivers"]) == 1
        entry = result["drivers"][0]
        assert entry["completedStops"] == 1
        assert entry["casesDelivered"] == 5
        assert entry["onTimeRate"] == 1.0

    async def test_driver_performance_requires_range(self, runtime: Runtime) -> None:
        from ontology_runtime.errors import ValidationFailed

        with pytest.raises(ValidationFailed) as exc:
            await runtime.run_function("driverPerformance", {})
        assert exc.value.violations[0]["code"] == "missing_parameter"

    async def test_forecast_and_credit(self, runtime: Runtime) -> None:
        ids = await _world(runtime)
        await runtime.apply(
            "CreateSalesOrder",
            {
                "outlet": ids["outlet"],
                "orderDate": dt.date.today().isoformat(),
                "lines": [{"productRid": ids["product"], "cases": 4}],
            },
        )
        forecast = await runtime.run_function(
            "forecastOutletDemand", {"outlet": ids["outlet"], "weeks": 4}
        )
        assert forecast["weeks"] == 4
        assert forecast["forecast"]

        credit = await runtime.run_function("scoreOutletCredit", {"outlet": ids["outlet"]})
        assert credit["orderCount"] == 1
        assert credit["riskBand"] == "low"


class TestProposalGuards:
    async def test_apply_proposal_rejects_wrong_type(self, runtime: Runtime) -> None:
        ids = await _world(runtime)
        from ontology_runtime.actions.context import EditContext
        from ontology_runtime.errors import ValidationFailed

        context = EditContext(runtime.registry, runtime.session, actor="t")
        with pytest.raises(ValidationFailed):
            await apply_approved_proposal(context, {"proposal": ids["outlet"]})

    async def test_apply_proposal_rejects_meta_actions(self, runtime: Runtime) -> None:
        from ontology_runtime.actions.context import EditContext
        from ontology_runtime.errors import ValidationFailed

        _ = await _world(runtime)
        proposal = await runtime.objects.create(
            "ActionProposal",
            {
                "proposalNo": "PR-GUARD",
                "actionType": "ApproveActionProposal",
                "params": {},
                "rationale": "self",
                "status": "proposed",
            },
        )
        context = EditContext(runtime.registry, runtime.session, actor="t")
        with pytest.raises(ValidationFailed):
            await apply_approved_proposal(context, {"proposal": proposal.rid})
