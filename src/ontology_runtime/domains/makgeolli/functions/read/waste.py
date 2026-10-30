"""Read functions: waste history."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ontology_runtime.actions.context import EditContext

REASON_NAMES = {
    "quality": "품질",
    "expiry": "유통기한",
    "damage": "파손",
    "other": "기타",
}


async def waste_history(
    context: EditContext,
    product: str | None = None,
    withinDays: int | None = None,
) -> dict[str, Any]:
    """Aggregate waste records by reason, optionally narrowed by product/window."""
    rows: list[dict[str, Any]] = []
    by_reason: dict[str, int] = {}
    total_quantity = 0
    for record in await context.search("WasteRecord"):
        wasted_on = dt.date.fromisoformat(str(record.properties["wastedOn"]))
        if withinDays is not None and wasted_on < dt.date.today() - dt.timedelta(
            days=int(withinDays)
        ):
            continue
        batch = await context.get(str(record.properties["batchRid"]))
        if product and (batch is None or batch.properties.get("productRid") != product):
            continue
        reason = str(record.properties.get("reason"))
        quantity = int(record.properties.get("quantity") or 0)
        by_reason[reason] = by_reason.get(reason, 0) + quantity
        total_quantity += quantity
        product_obj = await context.get(str(batch.properties["productRid"])) if batch else None
        rows.append(
            {
                "rid": record.rid,
                "wasteNo": record.properties.get("wasteNo"),
                "wastedOn": wasted_on.isoformat(),
                "batchNo": batch.properties.get("batchNo") if batch else None,
                "product": product_obj.properties.get("name") if product_obj else None,
                "quantity": quantity,
                "reason": reason,
                "reasonName": REASON_NAMES.get(reason, reason),
            }
        )
    rows.sort(key=lambda row: row["wastedOn"], reverse=True)
    return {
        "count": len(rows),
        "totalQuantity": total_quantity,
        "byReason": by_reason,
        "records": rows,
    }
