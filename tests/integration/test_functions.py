"""Domain functions: money math, route planning, invoices, and exceptions."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.config import SCHEMA_DIR
from ontology_runtime.functions.write.delivery import haversine_km, nearest_neighbour_route
from ontology_runtime.registry import SchemaRegistry
from ontology_runtime.runtime import Runtime


@pytest.fixture
def runtime(session: AsyncSession) -> Runtime:
    return Runtime(SchemaRegistry.from_directory(SCHEMA_DIR), session)


async def _seed_master(runtime: Runtime) -> dict[str, str]:
    depot = await runtime.objects.create(
        "Depot",
        {
            "depotNo": "D1",
            "name": "서울창고",
            "region": "수도권",
            "lat": 37.5,
            "lon": 127.0,
            "capacityCases": 5000,
        },
    )
    rep = await runtime.objects.create(
        "SalesRep",
        {"employeeNo": "R1", "name": "김영업", "depotRid": depot.rid, "status": "active"},
    )
    product_taxed = await runtime.objects.create(
        "Product",
        {
            "sku": "SOJU-360",
            "name": "참이슬 360ml",
            "category": "소주",
            "manufacturer": "하이트진로",
            "volumeMl": 360,
            "unitsPerCase": 30,
            "unitPrice": 1200,
            "casePrice": 36000,
            "taxType": "과세",
            "active": True,
        },
    )
    product_free = await runtime.objects.create(
        "Product",
        {
            "sku": "WINE-750",
            "name": "수입와인",
            "category": "와인",
            "manufacturer": "수입사",
            "volumeMl": 750,
            "unitsPerCase": 6,
            "unitPrice": 20000,
            "casePrice": 120000,
            "taxType": "면세",
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
    return {
        "depot": depot.rid,
        "rep": rep.rid,
        "taxed": product_taxed.rid,
        "free": product_free.rid,
        "outlet": outlet.rid,
    }


async def test_compute_order_totals_tax_math(runtime: Runtime) -> None:
    ids = await _seed_master(runtime)
    taxed_line = await runtime.objects.create(
        "SalesOrderLine",
        {
            "lineNo": "L1",
            "orderedCases": 2,
            "unitPrice": 36000,
            "lineAmount": 72000,
            "productName": "참이슬",
            "productRid": ids["taxed"],
        },
    )
    free_line = await runtime.objects.create(
        "SalesOrderLine",
        {
            "lineNo": "L2",
            "orderedCases": 1,
            "unitPrice": 120000,
            "lineAmount": 120000,
            "productName": "와인",
            "productRid": ids["free"],
        },
    )
    result = await runtime.run_function(
        "computeOrderTotals", {"orderLines": [taxed_line.rid, free_line.rid]}
    )
    assert result["subtotal"] == 192000
    assert result["tax"] == 7200  # 10% of only the taxable lines
    assert result["total"] == 199200
    assert result["totalCases"] == 3


async def test_validate_order_line_flags_inactive(runtime: Runtime) -> None:
    ids = await _seed_master(runtime)
    await runtime.objects.update(ids["taxed"], {"active": False})
    result = await runtime.run_function("validateOrderLine", {"product": ids["taxed"], "cases": 1})
    assert result["valid"] is False
    assert result["violations"][0]["code"] == "product_inactive"


async def test_create_sales_order_action(runtime: Runtime) -> None:
    ids = await _seed_master(runtime)
    result = await runtime.apply(
        "CreateSalesOrder",
        {
            "outlet": ids["outlet"],
            "orderDate": "2026-10-27",
            "requestedDeliveryDate": "2026-10-28",
            "channel": "phone",
            "lines": [{"productRid": ids["taxed"], "cases": 10}],
        },
        actor="rep01",
    )
    assert result.status == "succeeded", result.violations
    order_rid = result.data["created"]["SalesOrder"][0]
    order = await runtime.objects.get(order_rid)
    assert order.properties["totalAmount"] == 360000
    assert order.properties["taxAmount"] == 36000
    assert order.properties["status"] == "draft"
    assert order.properties["orderNo"].startswith("SO-20261027")

    lines = await runtime.links.targets(runtime.registry.link_on("SalesOrder", "lines"), order_rid)
    assert len(lines) == 1
    assert lines[0].properties["lineAmount"] == 360000


async def test_plan_deliveries_creates_delivery_with_stops(runtime: Runtime) -> None:
    ids = await _seed_master(runtime)
    await runtime.objects.create(
        "Driver",
        {
            "employeeNo": "DR1",
            "name": "박기사",
            "employmentType": "직영",
            "licenseType": "1종보통",
            "status": "available",
            "depotRid": ids["depot"],
        },
    )
    await runtime.objects.create(
        "Vehicle",
        {
            "plateNo": "12가3456",
            "vehicleType": "1톤탑차",
            "capacityCases": 100,
            "capacityWeightKg": 1000,
            "status": "available",
            "depotRid": ids["depot"],
        },
    )
    # 2026-10-27 is a Tuesday (weekday 1), matching the outlet.
    created = await runtime.apply(
        "CreateSalesOrder",
        {
            "outlet": ids["outlet"],
            "orderDate": "2026-10-26",
            "requestedDeliveryDate": "2026-10-27",
            "lines": [{"productRid": ids["taxed"], "cases": 5}],
        },
    )
    order_rid = created.data["created"]["SalesOrder"][0]
    submit = await runtime.apply("SubmitSalesOrder", {"order": order_rid})
    assert submit.status == "succeeded", submit.violations
    confirm = await runtime.apply("ConfirmSalesOrder", {"order": order_rid})
    assert confirm.status == "succeeded", confirm.violations
    order = await runtime.objects.get(order_rid)
    assert order.properties["status"] == "confirmed", order.properties

    plan = await runtime.apply(
        "PlanDeliveries", {"deliveryDate": "2026-10-27", "depot": ids["depot"]}
    )
    assert plan.status == "succeeded", plan.violations
    deliveries = await runtime.search("Delivery")
    assert len(deliveries.objects) == 1
    delivery = deliveries.objects[0]
    assert delivery.properties["totalStops"] == 1
    stops = await runtime.links.targets(runtime.registry.link_on("Delivery", "stops"), delivery.rid)
    assert len(stops) == 1
    assert stops[0].properties["outletRid"] == ids["outlet"]


async def test_complete_stop_issues_invoice(runtime: Runtime) -> None:
    ids = await _seed_master(runtime)
    delivery = await runtime.objects.create(
        "Delivery",
        {
            "deliveryNo": "DL-1",
            "deliveryDate": "2026-10-27",
            "depotRid": ids["depot"],
            "status": "in_progress",
            "totalCases": 4,
            "totalStops": 1,
        },
    )
    created = await runtime.apply(
        "CreateSalesOrder",
        {
            "outlet": ids["outlet"],
            "orderDate": "2026-10-26",
            "lines": [{"productRid": ids["taxed"], "cases": 4}],
        },
    )
    order_rid = created.data["created"]["SalesOrder"][0]
    stop = await runtime.objects.create(
        "DeliveryStop",
        {
            "stopNo": "DL-1-01",
            "sequence": 1,
            "status": "arrived",
            "plannedCases": 4,
            "outletRid": ids["outlet"],
            "deliveryRid": delivery.rid,
        },
    )
    await runtime.links.create("orderStop", order_rid, stop.rid)
    await runtime.links.create("outletStops", ids["outlet"], stop.rid)

    result = await runtime.apply("CompleteStop", {"stop": stop.rid, "actualCases": 3})
    assert result.status == "succeeded", result.violations

    invoices = await runtime.search("SalesInvoice")
    assert invoices.total == 1
    invoice = invoices.objects[0]
    assert invoice.properties["totalCases"] == 3
    assert invoice.properties["totalAmount"] == 108000  # 3 cases x 36000

    order = await runtime.objects.get(order_rid)
    assert order.properties["status"] == "partially_fulfilled"


async def test_complete_stop_rejects_over_delivery(runtime: Runtime) -> None:
    ids = await _seed_master(runtime)
    delivery = await runtime.objects.create(
        "Delivery",
        {
            "deliveryNo": "DL-2",
            "deliveryDate": "2026-10-27",
            "depotRid": ids["depot"],
            "status": "in_progress",
        },
    )
    stop = await runtime.objects.create(
        "DeliveryStop",
        {
            "stopNo": "DL-2-01",
            "sequence": 1,
            "status": "arrived",
            "plannedCases": 2,
            "outletRid": ids["outlet"],
            "deliveryRid": delivery.rid,
        },
    )
    result = await runtime.apply("CompleteStop", {"stop": stop.rid, "actualCases": 5})
    assert result.status == "failed"
    assert result.violations[0]["path"] == "actualCases"


async def test_vehicle_capacity(runtime: Runtime) -> None:
    ids = await _seed_master(runtime)
    vehicle = await runtime.objects.create(
        "Vehicle",
        {
            "plateNo": "99나9999",
            "vehicleType": "1톤탑차",
            "capacityCases": 10,
            "capacityWeightKg": 1000,
            "status": "available",
            "depotRid": ids["depot"],
        },
    )
    stops = []
    for index in range(3):
        stops.append(
            (
                await runtime.objects.create(
                    "DeliveryStop",
                    {
                        "stopNo": f"CAP-{index}",
                        "sequence": index + 1,
                        "status": "planned",
                        "plannedCases": 4,
                        "outletRid": ids["outlet"],
                        "deliveryRid": "ri.liquor.object.delivery.placeholder",
                    },
                )
            ).rid
        )
    result = await runtime.run_function(
        "checkVehicleCapacity", {"vehicle": vehicle.rid, "stops": stops}
    )
    assert result["fits"] is False
    assert result["requiredCases"] == 12
    assert result["capacityCases"] == 10


async def test_exception_detection_finds_unassigned_orders(runtime: Runtime) -> None:
    ids = await _seed_master(runtime)
    created = await runtime.apply(
        "CreateSalesOrder",
        {
            "outlet": ids["outlet"],
            "orderDate": "2026-10-26",
            "requestedDeliveryDate": "2026-10-27",
            "lines": [{"productRid": ids["taxed"], "cases": 2}],
        },
    )
    order_rid = created.data["created"]["SalesOrder"][0]
    await runtime.apply("SubmitSalesOrder", {"order": order_rid})
    await runtime.apply("ConfirmSalesOrder", {"order": order_rid})

    result = await runtime.run_function("detectDeliveryExceptions", {"deliveryDate": "2026-10-28"})
    assert any(item["orderRid"] == order_rid for item in result["unassignedOrders"])


def test_nearest_neighbour_is_deterministic() -> None:
    depot = (37.5, 127.0)
    points = [("b", 37.51, 127.01), ("a", 37.51, 127.01), ("c", 37.6, 127.2)]
    first = nearest_neighbour_route(depot, points)
    second = nearest_neighbour_route(depot, list(reversed(points)))
    assert [p[0] for p in first] == ["a", "b", "c"]
    assert first == second


def test_haversine_reasonable() -> None:
    # Seoul to Busan is roughly 325 km.
    assert 300 < haversine_km(37.5665, 126.9780, 35.1796, 129.0756) < 350


async def test_driver_shift_created_on_start(runtime: Runtime) -> None:
    ids = await _seed_master(runtime)
    driver = await runtime.objects.create(
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
            "driverRid": driver.rid,
            "status": "dispatched",
        },
    )
    result = await runtime.apply("StartDelivery", {"delivery": delivery.rid})
    assert result.status == "succeeded", result.violations
    shifts = await runtime.search("DriverShift")
    assert shifts.total == 1
    assert shifts.objects[0].properties["status"] == "working"
    updated = await runtime.objects.get(delivery.rid)
    assert updated.properties["status"] == "in_progress"
