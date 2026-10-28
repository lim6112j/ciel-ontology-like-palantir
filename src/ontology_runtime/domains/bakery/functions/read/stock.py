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
