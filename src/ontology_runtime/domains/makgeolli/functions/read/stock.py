"""Read functions: stock visibility (warehouse, outlet) and expiring batches."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ontology_runtime.actions.context import EditContext

#: Statuses that still represent sellable warehouse stock.
LIVE_STATUSES = {"ready"}


async def expiring_batches(context: EditContext, withinDays: int = 3) -> dict[str, Any]:
    """Return bottled batches whose expiry falls within `withinDays` of today.

    Rows carry both the display name (`product`) and the rid (`productRid`):
    humans read the name, agents reuse the rid to propose actions.
    """
    horizon = dt.date.today() + dt.timedelta(days=int(withinDays))
    product_names: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    for batch in await context.search("Batch"):
        if batch.properties.get("status") not in LIVE_STATUSES:
            continue
        expires = batch.properties.get("expiresOn")
        if not expires:
            continue
        expires_on = dt.date.fromisoformat(str(expires))
        if expires_on > horizon:
            continue
        product_rid = str(batch.properties.get("productRid"))
        if product_rid not in product_names:
            product_obj = await context.get(product_rid)
            product_names[product_rid] = (
                str(product_obj.properties.get("name")) if product_obj else ""
            )
        rows.append(
            {
                "rid": batch.rid,
                "batchNo": batch.properties.get("batchNo"),
                "product": product_names[product_rid],
                "productRid": product_rid,
                "bottledQty": batch.properties.get("bottledQty"),
                "expiresOn": expires_on.isoformat(),
                "daysLeft": (expires_on - dt.date.today()).days,
            }
        )
    rows.sort(key=lambda row: row["expiresOn"])
    return {"count": len(rows), "batches": rows}


async def warehouse_stock(
    context: EditContext,
    product: str | None = None,
) -> dict[str, Any]:
    """Return warehouse stock rows in FEFO (earliest expiry first) order."""
    rows: list[dict[str, Any]] = []
    product_names: dict[str, str] = {}
    for stock in await context.search("WarehouseStock"):
        stock_product = str(stock.properties.get("productRid"))
        if product and stock_product != product:
            continue
        if stock_product not in product_names:
            product_obj = await context.get(stock_product)
            product_names[stock_product] = (
                str(product_obj.properties.get("name")) if product_obj else ""
            )
        batch = await context.get(str(stock.properties.get("batchRid")))
        rows.append(
            {
                "rid": stock.rid,
                "stockNo": stock.properties.get("stockNo"),
                "product": product_names[stock_product],
                "productRid": stock_product,
                "batchNo": batch.properties.get("batchNo") if batch else None,
                "batchRid": stock.properties.get("batchRid"),
                "quantity": stock.properties.get("quantity"),
                "expiresOn": batch.properties.get("expiresOn") if batch else None,
                "updatedOn": stock.properties.get("updatedOn"),
            }
        )
    rows.sort(key=lambda row: (row["expiresOn"] or "9999-12-31", str(row["stockNo"])))
    total = sum(int(row["quantity"] or 0) for row in rows)
    return {"count": len(rows), "total": total, "stocks": rows}


async def outlet_stock(
    context: EditContext,
    customer: str,
    product: str | None = None,
) -> dict[str, Any]:
    """Return the stock rows of a customer, optionally narrowed to one product."""
    customer_obj = await context.require(customer)
    rows: list[dict[str, Any]] = []
    for stock in await context.search("OutletStock"):
        if stock.properties.get("customerRid") != customer_obj.rid:
            continue
        if product and stock.properties.get("productRid") != product:
            continue
        product_obj = await context.get(str(stock.properties.get("productRid")))
        rows.append(
            {
                "rid": stock.rid,
                "stockNo": stock.properties.get("stockNo"),
                "product": product_obj.properties.get("name") if product_obj else None,
                "quantity": stock.properties.get("quantity"),
                "updatedOn": stock.properties.get("updatedOn"),
            }
        )
    rows.sort(key=lambda row: str(row["stockNo"]))
    total = sum(int(row["quantity"] or 0) for row in rows)
    return {
        "customer": customer_obj.properties.get("name"),
        "count": len(rows),
        "total": total,
        "stocks": rows,
    }
