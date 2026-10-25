"""Write functions for delivery planning and execution."""

from __future__ import annotations

import datetime as dt
import math
from typing import Any

from ontology_runtime.actions.context import EditContext
from ontology_runtime.errors import ValidationFailed

DEFAULT_MAX_STOPS = 25
AVERAGE_SPEED_KMH = 30.0
SERVICE_MINUTES_PER_STOP = 12
DAY_START_HOUR = 8
EARTH_RADIUS_KM = 6371.0


def _require(path: str, message: str) -> ValidationFailed:
    return ValidationFailed([{"code": "invalid", "path": path, "message": message}])


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def weekday_of(date_value: str) -> int:
    """0=Monday ... 6=Sunday, matching Outlet.deliveryWeekday."""
    return dt.date.fromisoformat(str(date_value)[:10]).weekday()


def nearest_neighbour_route(
    depot: tuple[float, float], points: list[tuple[str, float, float]]
) -> list[tuple[str, float, float]]:
    """Deterministic nearest-neighbour ordering with an RID tie-break."""
    remaining = sorted(points, key=lambda p: p[0])
    ordered: list[tuple[str, float, float]] = []
    current = depot
    while remaining:
        remaining.sort(key=lambda p: (haversine_km(current[0], current[1], p[1], p[2]), p[0]))
        chosen = remaining.pop(0)
        ordered.append(chosen)
        current = (chosen[1], chosen[2])
    return ordered


async def plan_deliveries(context: EditContext, params: dict[str, Any]) -> None:
    """Plan a day's deliveries: select orders, order stops, pack vehicles."""
    delivery_date = str(params["deliveryDate"])[:10]
    depot_rid = params["depot"]
    max_stops = int(params.get("maxStopsPerVehicle") or DEFAULT_MAX_STOPS)

    depot = await context.require(depot_rid)
    depot_point = _point(depot)
    target_weekday = weekday_of(delivery_date)

    candidates, unassigned = await _collect_candidates(
        context, depot_rid, delivery_date, target_weekday
    )
    if not candidates:
        raise _require(
            "deliveryDate",
            f"{delivery_date} ({target_weekday})에 배차할 확정 발주가 없습니다.",
        )

    by_outlet = _group_by_outlet(candidates)
    ordered = nearest_neighbour_route(
        depot_point,
        [
            (
                rid,
                float(entry["outlet"].properties["lat"]),
                float(entry["outlet"].properties["lon"]),
            )
            for rid, entry in by_outlet.items()
        ],
    )

    drivers, vehicles = await _available_fleet(context, depot_rid)
    runs = _pack_runs(ordered, by_outlet, vehicles, max_stops)

    created = []
    for run_index, run in enumerate(runs):
        created.append(
            await _create_delivery(
                context,
                delivery_date=delivery_date,
                depot_rid=depot_rid,
                depot_point=depot_point,
                run_index=run_index,
                run=run,
                by_outlet=by_outlet,
                driver=drivers[run_index % len(drivers)],
                vehicle=vehicles[min(run_index, len(vehicles) - 1)],
            )
        )

    context.scratch["plannedDeliveries"] = created
    context.scratch["unassignedOutlets"] = sorted(unassigned)


def _point(obj: Any) -> tuple[float, float]:
    return float(obj.properties["lat"]), float(obj.properties["lon"])


async def _collect_candidates(
    context: EditContext, depot_rid: str, delivery_date: str, target_weekday: int
) -> tuple[list[tuple[Any, Any]], list[str]]:
    """Orders that are confirmed, due, unassigned, and belong to this depot/day."""
    confirmed = await context.search(
        "SalesOrder", {"field": "status", "op": "eq", "value": "confirmed"}
    )
    candidates: list[tuple[Any, Any]] = []
    unassigned: list[str] = []
    for order in confirmed:
        outlet_rid = order.properties.get("outletRid")
        if not outlet_rid:
            continue
        requested = order.properties.get("requestedDeliveryDate")
        if requested and str(requested) > delivery_date:
            continue
        if await context.linked(order.rid, "stop"):
            continue
        outlet = await context.get(outlet_rid)
        if outlet is None or outlet.properties.get("depotRid") != depot_rid:
            continue
        weekday = outlet.properties.get("deliveryWeekday")
        if weekday is not None and int(weekday) != target_weekday:
            continue
        if outlet.properties.get("lat") is None or outlet.properties.get("lon") is None:
            unassigned.append(outlet.rid)
            continue
        candidates.append((order, outlet))
    return candidates, unassigned


def _group_by_outlet(candidates: list[tuple[Any, Any]]) -> dict[str, dict[str, Any]]:
    by_outlet: dict[str, dict[str, Any]] = {}
    for order, outlet in candidates:
        entry = by_outlet.setdefault(outlet.rid, {"outlet": outlet, "orders": [], "cases": 0})
        entry["orders"].append(order)
        entry["cases"] += int(order.properties.get("totalCases") or 0)
    return by_outlet


async def _available_fleet(context: EditContext, depot_rid: str) -> tuple[list[Any], list[Any]]:
    drivers = [
        d
        for d in await context.search("Driver")
        if d.properties.get("depotRid") == depot_rid and d.properties.get("status") == "available"
    ]
    vehicles = [
        v
        for v in await context.search("Vehicle")
        if v.properties.get("depotRid") == depot_rid and v.properties.get("status") == "available"
    ]
    if not drivers:
        raise _require("depot", "가용한 기사가 없습니다.")
    if not vehicles:
        raise _require("depot", "가용한 차량이 없습니다.")
    return drivers, vehicles


def _pack_runs(
    ordered: list[tuple[str, float, float]],
    by_outlet: dict[str, dict[str, Any]],
    vehicles: list[Any],
    max_stops: int,
) -> list[list[tuple[str, float, float]]]:
    """Split the ordered route into capacity- and stop-bounded runs."""
    runs: list[list[tuple[str, float, float]]] = []
    current: list[tuple[str, float, float]] = []
    current_cases = 0
    vehicle_index = 0
    capacity = int(vehicles[0].properties.get("capacityCases") or 0)

    for point in ordered:
        stop_cases = int(by_outlet[point[0]]["cases"])
        if current and (current_cases + stop_cases > capacity or len(current) >= max_stops):
            runs.append(current)
            current = []
            current_cases = 0
            vehicle_index = min(vehicle_index + 1, len(vehicles) - 1)
            capacity = int(vehicles[vehicle_index].properties.get("capacityCases") or 0)
        current.append(point)
        current_cases += stop_cases
    if current:
        runs.append(current)
    return runs


async def _create_delivery(
    context: EditContext,
    *,
    delivery_date: str,
    depot_rid: str,
    depot_point: tuple[float, float],
    run_index: int,
    run: list[tuple[str, float, float]],
    by_outlet: dict[str, dict[str, Any]],
    driver: Any,
    vehicle: Any,
) -> dict[str, Any]:
    delivery_no = f"DL-{delivery_date.replace('-', '')}-{run_index + 1:03d}"
    distance, duration = _route_metrics(depot_point, run)
    total_cases = sum(int(by_outlet[point[0]]["cases"]) for point in run)

    delivery_rid = context.create(
        "Delivery",
        {
            "deliveryNo": delivery_no,
            "deliveryDate": delivery_date,
            "depotRid": depot_rid,
            "driverRid": driver.rid,
            "vehicleRid": vehicle.rid,
            "status": "planned",
            "plannedDistanceKm": round(distance, 2),
            "plannedDurationMin": duration,
            "totalStops": len(run),
            "totalCases": total_cases,
        },
    )
    context.link("deliveryDriver", delivery_rid, driver.rid)
    context.link("deliveryVehicle", delivery_rid, vehicle.rid)
    context.link("deliveryDepot", delivery_rid, depot_rid)

    await _create_stops(
        context,
        delivery_date=delivery_date,
        delivery_no=delivery_no,
        delivery_rid=delivery_rid,
        run=run,
        by_outlet=by_outlet,
        depot_point=depot_point,
    )

    return {
        "deliveryRid": delivery_rid,
        "deliveryNo": delivery_no,
        "driverRid": driver.rid,
        "vehicleRid": vehicle.rid,
        "stops": len(run),
        "cases": total_cases,
        "distanceKm": round(distance, 2),
        "durationMin": duration,
    }


async def _create_stops(
    context: EditContext,
    *,
    delivery_date: str,
    delivery_no: str,
    delivery_rid: str,
    run: list[tuple[str, float, float]],
    by_outlet: dict[str, dict[str, Any]],
    depot_point: tuple[float, float],
) -> None:
    clock = dt.datetime.combine(
        dt.date.fromisoformat(delivery_date),
        dt.time(hour=DAY_START_HOUR),
        tzinfo=dt.UTC,
    )
    current = depot_point
    for step, (outlet_rid, lat, lon) in enumerate(run, start=1):
        clock += dt.timedelta(
            minutes=(haversine_km(current[0], current[1], lat, lon) / AVERAGE_SPEED_KMH) * 60
            + SERVICE_MINUTES_PER_STOP
        )
        entry = by_outlet[outlet_rid]
        stop_rid = context.create(
            "DeliveryStop",
            {
                "stopNo": f"{delivery_no}-{step:02d}",
                "sequence": step,
                "status": "planned",
                "plannedAt": clock.isoformat(),
                "plannedCases": int(entry["cases"]),
                "outletRid": outlet_rid,
                "deliveryRid": delivery_rid,
            },
        )
        context.link("deliveryStops", delivery_rid, stop_rid)
        context.link("outletStops", outlet_rid, stop_rid)
        for order in entry["orders"]:
            context.link("orderStop", order.rid, stop_rid)
        current = (lat, lon)


def _route_metrics(
    depot: tuple[float, float], run: list[tuple[str, float, float]]
) -> tuple[float, int]:
    distance = 0.0
    current = depot
    for _rid, lat, lon in run:
        distance += haversine_km(current[0], current[1], lat, lon)
        current = (lat, lon)
    distance += haversine_km(current[0], current[1], depot[0], depot[1])
    minutes = int(distance / AVERAGE_SPEED_KMH * 60) + SERVICE_MINUTES_PER_STOP * len(run)
    return distance, minutes


async def complete_stop(context: EditContext, params: dict[str, Any]) -> None:
    stop = await context.require(params["stop"])
    if stop.object_type != "DeliveryStop":
        raise _require("stop", "DeliveryStop 객체가 아닙니다.")
    if stop.properties.get("status") not in {"planned", "arrived"}:
        raise _require("stop", f"이미 {stop.properties.get('status')} 상태인 정류장입니다.")

    actual_cases = int(params["actualCases"])
    planned_cases = int(stop.properties.get("plannedCases") or 0)
    if actual_cases > planned_cases:
        raise _require(
            "actualCases", f"실제 납품 케이스({actual_cases})가 계획({planned_cases})을 초과합니다."
        )

    now = dt.datetime.now(dt.UTC).isoformat()
    await context.modify(
        stop.rid,
        {"status": "completed", "actualCases": actual_cases, "completedAt": now},
    )

    delivery_rid = stop.properties.get("deliveryRid")
    if delivery_rid:
        delivery = await context.get(delivery_rid)
        if delivery is not None:
            await context.modify(delivery_rid, {"status": "in_progress"})

    await _issue_invoice(context, stop, actual_cases)


async def _issue_invoice(context: EditContext, stop: Any, actual_cases: int) -> None:
    outlet_rid = stop.properties["outletRid"]
    orders = await context.linked(stop.rid, "orders")
    if not orders:
        return

    sequence = len(await context.search("SalesInvoice")) + 1
    invoice_no = f"INV-{dt.date.today().strftime('%Y%m%d')}-{sequence:04d}"

    line_specs: list[dict[str, Any]] = []
    for order in orders:
        lines = await context.linked(order.rid, "lines")
        for line in lines:
            line_specs.append(
                {
                    "productRid": line.properties.get("productRid"),
                    "orderedCases": int(line.properties.get("orderedCases") or 0),
                    "unitPrice": int(line.properties.get("unitPrice") or 0),
                    "orderLineRid": line.rid,
                    "orderRid": order.rid,
                    "productName": line.properties.get("productName"),
                }
            )
    if not line_specs:
        return

    remaining = actual_cases
    delivered_specs = []
    for index, spec in enumerate(line_specs):
        if index == len(line_specs) - 1:
            delivered = remaining
        else:
            delivered = min(spec["orderedCases"], remaining)
        remaining = max(0, remaining - delivered)
        delivered_specs.append({**spec, "deliveredCases": delivered})

    subtotal = sum(spec["deliveredCases"] * spec["unitPrice"] for spec in delivered_specs)
    taxable_subtotal = 0
    for spec in delivered_specs:
        product = await context.get(spec["productRid"])
        if product is None or product.properties.get("taxType") != "면세":
            taxable_subtotal += spec["deliveredCases"] * spec["unitPrice"]
    tax = taxable_subtotal * 10 // 100

    invoice_rid = context.create(
        "SalesInvoice",
        {
            "invoiceNo": invoice_no,
            "issueDate": dt.date.today().isoformat(),
            "totalAmount": subtotal,
            "taxAmount": tax,
            "totalCases": actual_cases,
            "status": "issued",
            "outletRid": outlet_rid,
        },
    )
    context.link("invoiceStop", invoice_rid, stop.rid)

    for index, spec in enumerate(delivered_specs, start=1):
        line_rid = context.create(
            "InvoiceLine",
            {
                "invoiceLineNo": f"{invoice_no}-{index:02d}",
                "deliveredCases": spec["deliveredCases"],
                "unitPrice": spec["unitPrice"],
                "lineAmount": spec["deliveredCases"] * spec["unitPrice"],
                "productRid": spec["productRid"],
                "orderLineRid": spec["orderLineRid"],
            },
        )
        context.link("invoiceLines", invoice_rid, line_rid)
        context.scratch[f"invoiceLineParent:{line_rid}"] = invoice_rid

    for order in orders:
        context.link("orderInvoice", order.rid, invoice_rid)
        ordered_total = sum(
            int(line.properties.get("orderedCases") or 0)
            for line in await context.linked(order.rid, "lines")
        )
        status = "fulfilled" if actual_cases >= ordered_total else "partially_fulfilled"
        await context.modify(order.rid, {"status": status})

    context.scratch.setdefault("invoices", []).append(invoice_rid)
