"""Read-only delivery functions: capacity checks and deterministic exception detection."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ontology_runtime.actions.context import EditContext

#: A stop is late once it is this many minutes past its planned arrival.
LATE_TOLERANCE_MIN = 30


def _parse(value: Any) -> dt.datetime | None:
    if not value:
        return None
    if isinstance(value, dt.datetime):
        return value
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


async def check_vehicle_capacity(
    context: EditContext, vehicle: str, stops: list[str] | None = None
) -> dict[str, Any]:
    vehicle_obj = await context.get(vehicle)
    if vehicle_obj is None:
        return {
            "fits": False,
            "violations": [
                {
                    "code": "vehicle_not_found",
                    "path": "vehicle",
                    "message": "차량을 찾을 수 없습니다.",
                }
            ],
        }

    capacity_cases = int(vehicle_obj.properties.get("capacityCases") or 0)
    required_cases = 0
    for rid in stops or []:
        stop = await context.get(rid)
        if stop is not None:
            required_cases += int(stop.properties.get("plannedCases") or 0)

    fits = required_cases <= capacity_cases
    violations = []
    if not fits:
        violations.append(
            {
                "code": "capacity_exceeded",
                "path": "stops",
                "message": (
                    f"필요 {required_cases}케이스가 적재 한도 {capacity_cases}케이스를 초과합니다."
                ),
            }
        )
    return {
        "fits": fits,
        "requiredCases": required_cases,
        "capacityCases": capacity_cases,
        "utilization": round(required_cases / capacity_cases, 3) if capacity_cases else 0.0,
        "violations": violations,
    }


async def detect_delivery_exceptions(
    context: EditContext, deliveryDate: str, depot: str | None = None
) -> dict[str, Any]:
    """Find problems deterministically; the agent decides what to do about them."""
    target_date = str(deliveryDate)
    now = dt.datetime.now(dt.UTC)

    deliveries = [
        d
        for d in await context.search(
            "Delivery", {"field": "deliveryDate", "op": "eq", "value": target_date}
        )
        if depot is None
        or d.properties.get("depotRid") == depot
        and d.properties.get("status") not in {"completed", "cancelled", "partially_completed"}
    ]

    late_stops: list[dict[str, Any]] = []
    failed_stops: list[dict[str, Any]] = []
    overcapacity: list[dict[str, Any]] = []

    for delivery in deliveries:
        stops = [
            s
            for s in await context.search("DeliveryStop")
            if s.properties.get("deliveryRid") == delivery.rid
        ]
        for stop in stops:
            planned = _parse(stop.properties.get("plannedAt"))
            completed = _parse(stop.properties.get("completedAt"))
            if (
                stop.properties.get("status") in {"planned", "arrived"}
                and planned is not None
                and now - planned > dt.timedelta(minutes=LATE_TOLERANCE_MIN)
            ):
                late_stops.append(
                    {
                        "stopRid": stop.rid,
                        "stopNo": stop.properties.get("stopNo"),
                        "deliveryRid": delivery.rid,
                        "minutesLate": int((now - planned).total_seconds() // 60),
                        "status": stop.properties.get("status"),
                    }
                )
            if stop.properties.get("status") == "failed" and completed is None:
                failed_stops.append(
                    {
                        "stopRid": stop.rid,
                        "stopNo": stop.properties.get("stopNo"),
                        "deliveryRid": delivery.rid,
                        "reason": stop.properties.get("failureReason"),
                    }
                )

        vehicle_rid = delivery.properties.get("vehicleRid")
        if vehicle_rid:
            capacity = await check_vehicle_capacity(context, vehicle_rid, [s.rid for s in stops])
            if not capacity["fits"]:
                overcapacity.append(
                    {
                        "deliveryRid": delivery.rid,
                        "deliveryNo": delivery.properties.get("deliveryNo"),
                        "requiredCases": capacity["requiredCases"],
                        "capacityCases": capacity["capacityCases"],
                    }
                )

    confirmed = await context.search(
        "SalesOrder", {"field": "status", "op": "eq", "value": "confirmed"}
    )
    unassigned = [
        {
            "orderRid": order.rid,
            "orderNo": order.properties.get("orderNo"),
            "requestedDeliveryDate": order.properties.get("requestedDeliveryDate"),
            "totalCases": order.properties.get("totalCases"),
        }
        for order in confirmed
        if str(order.properties.get("requestedDeliveryDate") or "") <= target_date
    ]

    return {
        "deliveryDate": target_date,
        "lateStops": late_stops,
        "failedStops": failed_stops,
        "overcapacityDeliveries": overcapacity,
        "unassignedOrders": unassigned,
        "total": len(late_stops) + len(failed_stops) + len(overcapacity) + len(unassigned),
    }
