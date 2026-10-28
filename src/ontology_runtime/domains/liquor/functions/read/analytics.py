"""Read-only analytics functions used by the copilot and exception agents."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ontology_runtime.actions.context import EditContext

FORECAST_DEFAULT_WEEKS = 4
ON_TIME_TOLERANCE_MIN = 30
#: Weighting of delivery failures vs. cancellations in the credit score.
FAILURE_WEIGHT = 0.6
CANCEL_WEIGHT = 0.4
HIGH_RISK_THRESHOLD = 0.6
MEDIUM_RISK_THRESHOLD = 0.3


def _date(value: Any) -> dt.date | None:
    if not value:
        return None
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _datetime(value: Any) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


async def driver_performance(context: EditContext, **kwargs: Any) -> dict[str, Any]:
    start = _date(kwargs.get("from"))
    end = _date(kwargs.get("to"))
    driver_rid = kwargs.get("driver")
    if start is None or end is None:
        return {
            "drivers": [],
            "violations": [
                {"code": "invalid_range", "path": "from", "message": "기간이 필요합니다."}
            ],
        }

    deliveries = await context.search("Delivery")
    stops = await context.search("DeliveryStop")

    driver_names: dict[str, dict[str, str]] = {}

    async def driver_labels(rid: str) -> dict[str, str]:
        if rid not in driver_names:
            driver = await context.get(rid)
            driver_names[rid] = (
                {
                    "driver": str(driver.properties.get("name")),
                    "employeeNo": str(driver.properties.get("employeeNo")),
                }
                if driver
                else {"driver": "", "employeeNo": ""}
            )
        return driver_names[rid]

    per_driver: dict[str, dict[str, Any]] = {}
    for delivery in deliveries:
        delivery_date = _date(delivery.properties.get("deliveryDate"))
        if delivery_date is None or not (start <= delivery_date <= end):
            continue
        rid = delivery.properties.get("driverRid")
        if not rid or (driver_rid and rid != driver_rid):
            continue
        entry = per_driver.setdefault(
            rid,
            {
                "driverRid": rid,
                "deliveries": 0,
                "completedStops": 0,
                "failedStops": 0,
                "onTimeStops": 0,
                "casesDelivered": 0,
            },
        )
        entry["deliveries"] += 1
        for stop in stops:
            if stop.properties.get("deliveryRid") != delivery.rid:
                continue
            status = stop.properties.get("status")
            if status == "completed":
                entry["completedStops"] += 1
                entry["casesDelivered"] += int(stop.properties.get("actualCases") or 0)
                planned = _datetime(stop.properties.get("plannedAt"))
                completed = _datetime(stop.properties.get("completedAt"))
                if (
                    planned
                    and completed
                    and (completed - planned).total_seconds() / 60 <= ON_TIME_TOLERANCE_MIN
                ):
                    entry["onTimeStops"] += 1
            elif status == "failed":
                entry["failedStops"] += 1

    results = []
    for rid, entry in per_driver.items():
        evaluated = entry["completedStops"] + entry["failedStops"]
        results.append(
            {
                **entry,
                **(await driver_labels(rid)),
                "onTimeRate": round(entry["onTimeStops"] / evaluated, 3) if evaluated else None,
            }
        )
    results.sort(key=lambda row: row["driverRid"])
    return {"from": start.isoformat(), "to": end.isoformat(), "drivers": results}


async def forecast_outlet_demand(
    context: EditContext, outlet: str, weeks: int | None = None
) -> dict[str, Any]:
    window = max(1, int(weeks or FORECAST_DEFAULT_WEEKS))
    horizon_start = dt.date.today() - dt.timedelta(weeks=window)

    orders = [
        o
        for o in await context.search("SalesOrder")
        if o.properties.get("outletRid") == outlet
        and o.properties.get("status") != "cancelled"
        and (_date(o.properties.get("orderDate")) or horizon_start) >= horizon_start
    ]
    by_product: dict[str, int] = {}
    for order in orders:
        for line in await context.linked(order.rid, "lines"):
            product = line.properties.get("productRid") or "unknown"
            by_product[product] = by_product.get(product, 0) + int(
                line.properties.get("orderedCases") or 0
            )

    outlet_obj = await context.get(outlet)
    outlet_name = str(outlet_obj.properties.get("name")) if outlet_obj else ""
    product_names: dict[str, str] = {}
    forecast = []
    for product, total in sorted(by_product.items()):
        if product not in product_names:
            product_obj = await context.get(product)
            product_names[product] = str(product_obj.properties.get("name")) if product_obj else ""
        forecast.append(
            {
                "product": product_names[product],
                "productRid": product,
                "weeklyAverageCases": round(total / window, 2),
                "windowWeeks": window,
                "totalCases": total,
            }
        )
    return {"outlet": outlet, "outletName": outlet_name, "weeks": window, "forecast": forecast}


async def score_outlet_credit(context: EditContext, outlet: str) -> dict[str, Any]:
    orders = [
        o for o in await context.search("SalesOrder") if o.properties.get("outletRid") == outlet
    ]
    stops = [
        s for s in await context.search("DeliveryStop") if s.properties.get("outletRid") == outlet
    ]

    total_stops = len(stops)
    failed = sum(1 for s in stops if s.properties.get("status") == "failed")
    cancelled = sum(1 for o in orders if o.properties.get("status") == "cancelled")
    lifetime_cases = sum(int(o.properties.get("totalCases") or 0) for o in orders)

    failure_rate = failed / total_stops if total_stops else 0.0
    cancel_rate = cancelled / len(orders) if orders else 0.0
    score = min(1.0, round(failure_rate * FAILURE_WEIGHT + cancel_rate * CANCEL_WEIGHT, 3))

    band = (
        "high"
        if score >= HIGH_RISK_THRESHOLD
        else "medium"
        if score >= MEDIUM_RISK_THRESHOLD
        else "low"
    )
    outlet_obj = await context.get(outlet)
    return {
        "outlet": outlet,
        "outletName": str(outlet_obj.properties.get("name")) if outlet_obj else "",
        "orderCount": len(orders),
        "stopCount": total_stops,
        "failureRate": round(failure_rate, 3),
        "cancelRate": round(cancel_rate, 3),
        "lifetimeCases": lifetime_cases,
        "riskScore": score,
        "riskBand": band,
    }
