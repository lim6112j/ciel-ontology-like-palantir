"""Read functions: batch stock visibility for the bakery domain."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ontology_runtime.actions.context import EditContext

#: Statuses that still represent sellable stock.
LIVE_STATUSES = {"planned", "baked"}


async def expiring_batches(context: EditContext, withinDays: int = 3) -> dict[str, Any]:
    """Return live batches whose expiry falls within `withinDays` of today."""
    horizon = dt.date.today() + dt.timedelta(days=int(withinDays))
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
        rows.append(
            {
                "rid": batch.rid,
                "batchNo": batch.properties.get("batchNo"),
                "productRid": batch.properties.get("productRid"),
                "quantity": batch.properties.get("quantity"),
                "expiresOn": expires_on.isoformat(),
                "daysLeft": (expires_on - dt.date.today()).days,
            }
        )
    rows.sort(key=lambda row: row["expiresOn"])
    return {"count": len(rows), "batches": rows}


async def store_stock(
    context: EditContext,
    store: str,
    product: str | None = None,
) -> dict[str, Any]:
    """Return the stock rows of a store, optionally narrowed to one product."""
    store_obj = await context.require(store)
    rows: list[dict[str, Any]] = []
    for stock in await context.search("StoreStock"):
        if stock.properties.get("storeRid") != store_obj.rid:
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
        "store": store_obj.properties.get("name"),
        "count": len(rows),
        "total": total,
        "stocks": rows,
    }


async def production_summary(context: EditContext, planDate: str | None = None) -> dict[str, Any]:
    """Summarize production plans (and their batches) for a date, defaulting to today."""
    target = planDate or dt.date.today().isoformat()
    plans: list[dict[str, Any]] = []
    for plan in await context.search("ProductionPlan"):
        if plan.properties.get("planDate") != target:
            continue
        product_obj = await context.get(str(plan.properties.get("productRid")))
        plans.append(
            {
                "rid": plan.rid,
                "planNo": plan.properties.get("planNo"),
                "product": product_obj.properties.get("name") if product_obj else None,
                "plannedQty": plan.properties.get("plannedQty"),
                "producedQty": plan.properties.get("producedQty"),
                "status": plan.properties.get("status"),
            }
        )
    plans.sort(key=lambda row: str(row["planNo"]))
    counts: dict[str, int] = {}
    for row in plans:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {"planDate": target, "count": len(plans), "byStatus": counts, "plans": plans}
