"""Read functions: sales analytics and reorder suggestions."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ontology_runtime.actions.context import EditContext

#: Reorder logic knobs.
DEMAND_WINDOW_DAYS = 14
SHORT_SHELF_LIFE_DAYS = 10


async def sales_summary(
    context: EditContext,
    withinDays: int = 30,
    customer: str | None = None,
) -> dict[str, Any]:
    """Summarize orders in the window: amount, volume, statuses, top products."""
    since = dt.date.today() - dt.timedelta(days=int(withinDays))
    total_amount = 0
    total_cases = 0
    by_status: dict[str, int] = {}
    by_product: dict[str, dict[str, Any]] = {}
    by_customer: dict[str, dict[str, Any]] = {}
    for order in await context.search("SalesOrder"):
        if customer and order.properties.get("customerRid") != customer:
            continue
        order_date = dt.date.fromisoformat(str(order.properties["orderDate"]))
        if order_date < since:
            continue
        status = str(order.properties.get("status"))
        if status == "cancelled":
            continue
        by_status[status] = by_status.get(status, 0) + 1
        amount = int(order.properties.get("totalAmount") or 0)
        total_amount += amount
        lines = await context.linked(order.rid, "lines")
        for line in lines:
            cases = int(line.properties.get("cases") or 0)
            total_cases += cases
            product_rid = str(line.properties.get("productRid"))
            entry = by_product.setdefault(
                product_rid,
                {"amount": 0, "cases": 0, "productName": line.properties.get("productName")},
            )
            entry["amount"] += int(line.properties.get("lineAmount") or 0)
            entry["cases"] += cases
            customer_rid = str(order.properties.get("customerRid"))
            customer_entry = by_customer.setdefault(customer_rid, {"amount": 0, "orders": 0})
            customer_entry["amount"] += int(line.properties.get("lineAmount") or 0)
            customer_entry["orders"] += 0

    top_products = sorted(
        ({"productRid": rid, **entry} for rid, entry in by_product.items()),
        key=lambda row: row["amount"],
        reverse=True,
    )
    return {
        "withinDays": int(withinDays),
        "orderCount": sum(by_status.values()),
        "byStatus": by_status,
        "totalAmount": total_amount,
        "totalCases": total_cases,
        "topProducts": top_products,
        "byCustomer": by_customer,
    }


async def reorder_suggestions(context: EditContext) -> dict[str, Any]:
    """Suggest brew volumes per active product from recent demand and pipeline time.

    Suggested volume is capped so a batch does not outlive a short shelf life:
    suggestion ≤ shipped demand (14d) scaled by shelfLifeDays / window.
    """
    today = dt.date.today()
    since = today - dt.timedelta(days=DEMAND_WINDOW_DAYS)

    shipped_by_product: dict[str, int] = {}
    for shipment in await context.search("Shipment"):
        if shipment.properties.get("status") == "cancelled":
            continue
        ship_date = shipment.properties.get("shipDate")
        if not ship_date or dt.date.fromisoformat(str(ship_date)) < since:
            continue
        batch = await context.get(str(shipment.properties["batchRid"]))
        if batch is None:
            continue
        product_rid = str(batch.properties["productRid"])
        shipped_by_product[product_rid] = shipped_by_product.get(product_rid, 0) + int(
            shipment.properties["quantity"]
        )

    warehouse_by_product: dict[str, int] = {}
    for stock in await context.search("WarehouseStock"):
        product_rid = str(stock.properties["productRid"])
        warehouse_by_product[product_rid] = warehouse_by_product.get(product_rid, 0) + int(
            stock.properties["quantity"]
        )

    suggestions: list[dict[str, Any]] = []
    for product in await context.search("Product"):
        if product.properties.get("active") is False:
            continue
        demand = shipped_by_product.get(product.rid, 0)
        warehouse = warehouse_by_product.get(product.rid, 0)
        shelf_life = int(product.properties["shelfLifeDays"])
        lead_days = int(product.properties["fermentationDays"]) + int(
            product.properties["agingDays"]
        )
        suggested_bottles = max(0, demand - warehouse)
        # A short shelf life means small, frequent batches: cap by what can
        # realistically be sold within the shelf life.
        cap = int(demand * shelf_life / DEMAND_WINDOW_DAYS) if demand else 0
        if cap:
            suggested_bottles = min(suggested_bottles, cap)
        suggested_l = round(suggested_bottles * int(product.properties["volumeMl"]) / 1000, 1)
        suggestions.append(
            {
                "productRid": product.rid,
                "product": product.properties["name"],
                "shelfLifeDays": shelf_life,
                "leadDays": lead_days,
                "recentShipped": demand,
                "warehouseStock": warehouse,
                "suggestedBottles": suggested_bottles,
                "suggestedVolumeL": suggested_l,
                "note": (
                    "짧은 유통기한: 소량 다빈도 양조 권장"
                    if shelf_life <= SHORT_SHELF_LIFE_DAYS and suggested_bottles > 0
                    else None
                ),
            }
        )
    suggestions.sort(key=lambda row: row["suggestedBottles"], reverse=True)
    return {"suggestions": suggestions}
