"""Write functions for temperature control: readings and target adjustments."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ontology_runtime.actions.context import EditContext
from ontology_runtime.domains.makgeolli.functions.write.common import (
    invalid,
    next_no,
)

READING_PREFIX = "TR"


def _target_range(batch: Any, stage: str) -> tuple[float, float]:
    if stage == "fermentation":
        return (
            float(batch.properties["fermentationTempC"]) - 1.0,
            float(batch.properties["fermentationTempC"]) + 1.0,
        )
    return (
        float(batch.properties["agingTempC"]) - 1.0,
        float(batch.properties["agingTempC"]) + 1.0,
    )


def _expected_stage(batch: Any, stage: str) -> bool:
    status = str(batch.properties.get("status") or "")
    if stage == "fermentation":
        return status == "fermenting"
    return status == "aging"


def _temp_in_target_range(temp: float, minimum: Any, maximum: Any) -> bool:
    return float(minimum) <= temp <= float(maximum)


async def record_temp_reading(context: EditContext, params: dict[str, Any]) -> None:
    batch = await context.require(params["batch"])
    if batch.object_type != "Batch":
        raise invalid("batch", "배치를 찾을 수 없습니다.")

    stage = params.get("stage")
    if stage not in {"fermentation", "aging"}:
        raise invalid("stage", "단계는 fermentation 또는 aging이어야 합니다.")
    if not _expected_stage(batch, stage):
        status = batch.properties.get("status")
        raise invalid("stage", f"{status} 상태 배치의 {stage} 온도를 측정할 수 없습니다.")

    temp_c = float(params["tempC"])
    minimum, maximum = _target_range(batch, stage)
    in_range = bool(minimum <= temp_c <= maximum)
    recorded_at = params.get("recordedAt") or (dt.datetime.now().isoformat(timespec="seconds"))

    reading_no = await next_no(context, "TempReading", READING_PREFIX)
    reading_rid = context.create(
        "TempReading",
        {
            "readingNo": reading_no,
            "batchRid": batch.rid,
            "recordedAt": str(recorded_at),
            "tempC": temp_c,
            "stage": stage,
            "inRange": in_range,
        },
    )
    context.link("batchTempReadings", batch.rid, reading_rid)
    context.scratch["readingId"] = reading_rid
    context.scratch["inRange"] = in_range


async def adjust_batch_temp(context: EditContext, params: dict[str, Any]) -> None:
    batch = await context.require(params["batch"])
    if batch.object_type != "Batch":
        raise invalid("batch", "배치를 찾을 수 없습니다.")

    stage = params.get("stage")
    if stage not in {"fermentation", "aging"}:
        raise invalid("stage", "단계는 fermentation 또는 aging이어야 합니다.")

    target_temp = float(params["targetTempC"])
    tank = await context.get(str(batch.properties.get("tankRid") or ""))
    if tank is not None and tank.properties.get("tempControl") is True:
        minimum = float(tank.properties["tempMinC"])
        maximum = float(tank.properties["tempMaxC"])
        if not minimum <= target_temp <= maximum:
            raise invalid(
                "targetTempC",
                f"탱크 조절범위({minimum}~{maximum}°C) 밖의 목표온도입니다.",
            )

    if stage == "fermentation":
        await context.modify(batch.rid, {"fermentationTempC": target_temp})
    else:
        await context.modify(batch.rid, {"agingTempC": target_temp})
    context.scratch["targetTempC"] = target_temp
