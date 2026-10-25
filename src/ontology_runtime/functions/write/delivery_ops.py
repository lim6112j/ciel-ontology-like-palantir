"""Write functions for delivery execution transitions."""

from __future__ import annotations

import datetime as dt
from typing import Any

from ontology_runtime.actions.context import EditContext
from ontology_runtime.errors import ValidationFailed

TERMINAL_STOP_STATES = {"completed", "failed"}


def _invalid(path: str, message: str) -> ValidationFailed:
    return ValidationFailed([{"code": "invalid", "path": path, "message": message}])


async def start_delivery(context: EditContext, params: dict[str, Any]) -> None:
    delivery = await context.require(params["delivery"])
    status = delivery.properties.get("status")
    if status not in {"planned", "dispatched"}:
        raise _invalid("delivery", f"{status} 상태에서는 배송을 시작할 수 없습니다.")

    now = dt.datetime.now(dt.UTC)
    await context.modify(
        delivery.rid,
        {"status": "in_progress", "startedAt": now.isoformat()},
    )

    driver_rid = delivery.properties.get("driverRid")
    if driver_rid:
        driver = await context.get(driver_rid)
        if driver is not None:
            existing = [
                shift
                for shift in await context.search("DriverShift")
                if shift.properties.get("driverRid") == driver_rid
                and shift.properties.get("shiftDate") == now.date().isoformat()
            ]
            if existing:
                await context.modify(
                    existing[0].rid, {"status": "working", "startedAt": now.isoformat()}
                )
            else:
                shift_rid = context.create(
                    "DriverShift",
                    {
                        "shiftNo": f"SH-{now.strftime('%Y%m%d')}-{driver_rid[-6:]}",
                        "shiftDate": now.date().isoformat(),
                        "startedAt": now.isoformat(),
                        "status": "working",
                        "driverRid": driver_rid,
                    },
                )
                context.link("driverShifts", driver_rid, shift_rid)


async def complete_delivery(context: EditContext, params: dict[str, Any]) -> None:
    delivery = await context.require(params["delivery"])
    if delivery.properties.get("status") != "in_progress":
        raise _invalid("delivery", "진행 중인 배송만 완료할 수 있습니다.")

    stops = [
        s
        for s in await context.search("DeliveryStop")
        if s.properties.get("deliveryRid") == delivery.rid
    ]
    open_stops = [s for s in stops if s.properties.get("status") not in TERMINAL_STOP_STATES]
    if open_stops:
        raise _invalid(
            "delivery",
            f"아직 처리되지 않은 정류장이 {len(open_stops)}개 있습니다.",
        )

    failed = [s for s in stops if s.properties.get("status") == "failed"]
    now = dt.datetime.now(dt.UTC).isoformat()
    await context.modify(
        delivery.rid,
        {
            "status": "partially_completed" if failed else "completed",
            "completedAt": now,
        },
    )

    driver_rid = delivery.properties.get("driverRid")
    if driver_rid:
        today = dt.date.today().isoformat()
        for shift in await context.search(
            "DriverShift", {"field": "driverRid", "op": "eq", "value": driver_rid}
        ):
            if (
                shift.properties.get("shiftDate") == today
                and shift.properties.get("status") == "working"
            ):
                await context.modify(shift.rid, {"status": "finished", "endedAt": now})


async def reassign_driver(context: EditContext, params: dict[str, Any]) -> None:
    delivery = await context.require(params["delivery"])
    if delivery.properties.get("status") in {"completed", "cancelled", "partially_completed"}:
        raise _invalid("delivery", "종료된 배송의 기사는 변경할 수 없습니다.")

    driver = await context.require(params["driver"])
    if driver.properties.get("status") != "available":
        raise _invalid("driver", f"{driver.properties.get('name')} 기사는 현재 배정할 수 없습니다.")

    updates: dict[str, Any] = {"driverRid": driver.rid}
    if params.get("vehicle"):
        vehicle = await context.require(params["vehicle"])
        if vehicle.properties.get("status") != "available":
            raise _invalid("vehicle", "차량이 가용 상태가 아닙니다.")
        updates["vehicleRid"] = vehicle.rid
        context.link("deliveryVehicle", delivery.rid, vehicle.rid)
    if params.get("reason"):
        updates["note"] = params["reason"]

    await context.modify(delivery.rid, updates)
    context.link("deliveryDriver", delivery.rid, driver.rid)


async def reassign_stop(context: EditContext, params: dict[str, Any]) -> None:
    stop = await context.require(params["stop"])
    if stop.properties.get("status") == "completed":
        raise _invalid("stop", "이미 완료된 정류장은 재배차할 수 없습니다.")

    target = await context.require(params["targetDelivery"])
    if target.properties.get("status") in {"completed", "cancelled", "partially_completed"}:
        raise _invalid("targetDelivery", "종료된 배송으로는 재배차할 수 없습니다.")

    source_delivery = stop.properties.get("deliveryRid")
    sequence = params.get("sequence")
    if sequence is None:
        existing = [
            s
            for s in await context.search("DeliveryStop")
            if s.properties.get("deliveryRid") == target.rid
        ]
        sequence = len(existing) + 1

    # Free the old sequence slot before claiming the new one (uniqueness invariant).
    await context.modify(stop.rid, {"sequence": 10_000 + int(sequence)})
    if source_delivery:
        context.unlink("deliveryStops", source_delivery, stop.rid)

    await context.modify(
        stop.rid,
        {"deliveryRid": target.rid, "sequence": int(sequence), "status": "planned"},
    )
    context.link("deliveryStops", target.rid, stop.rid)
