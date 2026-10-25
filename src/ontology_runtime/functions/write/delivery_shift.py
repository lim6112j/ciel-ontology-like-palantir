"""Driver shift recording used when a delivery starts."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ontology_runtime.actions.context import EditContext


async def record_driver_shift(context: EditContext, params: dict[str, Any]) -> None:
    driver_rid = params["driver"]
    shift_date = str(params["shiftDate"])[:10]
    existing = await context.search(
        "DriverShift",
        {
            "and": [
                {"field": "driverRid", "op": "eq", "value": driver_rid},
                {"field": "shiftDate", "op": "eq", "value": shift_date},
            ]
        },
    )
    if existing:
        context.scratch["shiftRid"] = existing[0].rid
        return

    now = dt.datetime.now(dt.UTC).isoformat()
    shift_rid = context.create(
        "DriverShift",
        {
            "shiftNo": f"SH-{shift_date.replace('-', '')}-{driver_rid[-6:]}",
            "shiftDate": shift_date,
            "startedAt": now,
            "status": "working",
            "driverRid": driver_rid,
        },
    )
    context.link("driverShifts", driver_rid, shift_rid)
    context.scratch["shiftRid"] = shift_rid
