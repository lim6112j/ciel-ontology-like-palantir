"""Read functions: fermentation/aging pipeline progress and temperature deviations."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ontology_runtime.actions.context import EditContext

ACTIVE_STATUSES = {"fermenting", "aging"}


async def production_pipeline(
    context: EditContext,
    status: str | None = None,
) -> dict[str, Any]:
    """Return active batches with per-stage progress toward their due dates."""
    today = dt.date.today()
    product_names: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    for batch in await context.search("Batch"):
        batch_status = batch.properties.get("status")
        if batch_status not in ACTIVE_STATUSES:
            continue
        if status and batch_status != status:
            continue
        product_rid = str(batch.properties.get("productRid"))
        if product_rid not in product_names:
            product_obj = await context.get(product_rid)
            product_names[product_rid] = (
                str(product_obj.properties.get("name")) if product_obj else ""
            )

        if batch_status == "fermenting":
            start = dt.date.fromisoformat(str(batch.properties["brewDate"]))
            due = dt.date.fromisoformat(str(batch.properties["fermentationDueOn"]))
            total_days = (due - start).days
            elapsed = (today - start).days
            stage = "fermentation"
            target_temp = batch.properties.get("fermentationTempC")
        else:
            ferment_end = dt.date.fromisoformat(
                str(batch.properties.get("fermentedOn") or batch.properties["fermentationDueOn"])
            )
            due = dt.date.fromisoformat(str(batch.properties["agingDueOn"]))
            total_days = max(1, (due - ferment_end).days)
            elapsed = (today - ferment_end).days
            stage = "aging"
            target_temp = batch.properties.get("agingTempC")

        progress = max(0, min(100, round(elapsed / total_days * 100))) if total_days > 0 else 100
        rows.append(
            {
                "rid": batch.rid,
                "batchNo": batch.properties.get("batchNo"),
                "product": product_names[product_rid],
                "productRid": product_rid,
                "status": batch_status,
                "stage": stage,
                "progressPercent": progress,
                "dueOn": due.isoformat(),
                "daysOverdue": max(0, (today - due).days),
                "targetTempC": target_temp,
                "volumeL": batch.properties.get("volumeL"),
            }
        )
    rows.sort(key=lambda row: row["dueOn"])
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {"count": len(rows), "byStatus": counts, "batches": rows}


async def temp_deviations(context: EditContext, withinDays: int = 7) -> dict[str, Any]:
    """Return recent out-of-range temperature readings with batch context."""
    since = dt.date.today() - dt.timedelta(days=int(withinDays))
    batch_names: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    for reading in await context.search("TempReading"):
        if reading.properties.get("inRange") is not False:
            continue
        recorded_at = str(reading.properties.get("recordedAt") or "")
        if recorded_at[:10] < since.isoformat():
            continue
        batch_rid = str(reading.properties.get("batchRid"))
        if batch_rid not in batch_names:
            batch = await context.get(batch_rid)
            product_obj = (
                await context.get(str(batch.properties.get("productRid"))) if batch else None
            )
            batch_names[batch_rid] = {
                "batchNo": batch.properties.get("batchNo") if batch else None,
                "product": product_obj.properties.get("name") if product_obj else None,
                "status": batch.properties.get("status") if batch else None,
                "targetTempC": (
                    batch.properties.get("fermentationTempC")
                    if reading.properties.get("stage") == "fermentation"
                    else batch.properties.get("agingTempC")
                )
                if batch
                else None,
            }
        info = batch_names[batch_rid]
        rows.append(
            {
                "rid": reading.rid,
                "readingNo": reading.properties.get("readingNo"),
                "batchRid": batch_rid,
                "batchNo": info["batchNo"],
                "product": info["product"],
                "batchStatus": info["status"],
                "stage": reading.properties.get("stage"),
                "tempC": reading.properties.get("tempC"),
                "targetTempC": info["targetTempC"],
                "recordedAt": recorded_at,
            }
        )
    rows.sort(key=lambda row: row["recordedAt"], reverse=True)
    return {"count": len(rows), "readings": rows}
