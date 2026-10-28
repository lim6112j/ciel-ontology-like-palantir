"""Read functions: waste-record visibility for the bakery domain."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ontology_runtime.actions.context import EditContext


async def waste_history(
    context: EditContext,
    product: str | None = None,
    withinDays: int | None = None,
) -> dict[str, Any]:
    """Return WasteRecord rows, optionally narrowed by product and recency."""
    cutoff: dt.date | None = (
        dt.date.today() - dt.timedelta(days=int(withinDays)) if withinDays is not None else None
    )
    product_names: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    for record in await context.search("WasteRecord"):
        batch = await context.get(str(record.properties.get("batchRid")))
        if batch is None:
            continue
        batch_product_rid = str(batch.properties.get("productRid"))
        if product and batch_product_rid != product:
            continue
        wasted_on = dt.date.fromisoformat(str(record.properties.get("wastedOn")))
        if cutoff and wasted_on < cutoff:
            continue
        if batch_product_rid not in product_names:
            product_obj = await context.get(batch_product_rid)
            product_names[batch_product_rid] = (
                str(product_obj.properties.get("name")) if product_obj else ""
            )
        rows.append(
            {
                "rid": record.rid,
                "wasteNo": record.properties.get("wasteNo"),
                "batchNo": batch.properties.get("batchNo"),
                "product": product_names[batch_product_rid],
                "quantity": record.properties.get("quantity"),
                "reason": record.properties.get("reason"),
                "wastedOn": wasted_on.isoformat(),
            }
        )
    rows.sort(key=lambda row: row["wastedOn"], reverse=True)
    by_reason: dict[str, int] = {}
    for row in rows:
        reason = str(row["reason"])
        by_reason[reason] = by_reason.get(reason, 0) + int(row["quantity"] or 0)
    total = sum(int(row["quantity"] or 0) for row in rows)
    return {"count": len(rows), "totalQuantity": total, "byReason": by_reason, "records": rows}
