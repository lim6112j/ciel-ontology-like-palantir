"""Driver shift recording used at delivery start."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.actions.context import EditContext
from ontology_runtime.domains.liquor.functions.write.delivery_shift import record_driver_shift
from ontology_runtime.registry import SchemaRegistry
from ontology_runtime.runtime import Runtime


@pytest.fixture
def runtime(session: AsyncSession) -> Runtime:
    return Runtime(SchemaRegistry.from_domain("liquor"), session)


async def _driver(runtime: Runtime) -> str:
    depot = await runtime.objects.create(
        "Depot",
        {"depotNo": "D1", "name": "창고", "region": "수도권", "lat": 37.5, "lon": 127.0},
    )
    driver = await runtime.objects.create(
        "Driver",
        {
            "employeeNo": "DR1",
            "name": "박기사",
            "employmentType": "직영",
            "licenseType": "1종보통",
            "status": "available",
            "depotRid": depot.rid,
        },
    )
    return driver.rid


async def test_start_delivery_records_shift(runtime: Runtime) -> None:
    driver_rid = await _driver(runtime)
    depot = (await runtime.search("Depot")).objects[0]
    delivery = await runtime.objects.create(
        "Delivery",
        {
            "deliveryNo": "DL-1",
            "deliveryDate": dt.date.today().isoformat(),
            "depotRid": depot.rid,
            "driverRid": driver_rid,
            "status": "dispatched",
        },
    )

    result = await runtime.apply("StartDelivery", {"delivery": delivery.rid})
    assert result.status == "succeeded", result.violations

    shifts = await runtime.search("DriverShift")
    assert shifts.total == 1
    shift = shifts.objects[0]
    assert shift.properties["status"] == "working"
    assert shift.properties["shiftDate"] == dt.date.today().isoformat()
    assert shift.properties["driverRid"] == driver_rid


async def test_record_driver_shift_is_idempotent_within_a_run(runtime: Runtime) -> None:
    driver_rid = await _driver(runtime)
    today = dt.date.today().isoformat()

    context = EditContext(runtime.registry, runtime.session, actor="test")
    await record_driver_shift(context, {"driver": driver_rid, "shiftDate": today})
    first_rid = context.scratch["shiftRid"]
    assert len(context.batch) == 2  # one create + one link

    await record_driver_shift(context, {"driver": driver_rid, "shiftDate": today})
    assert context.scratch["shiftRid"] == first_rid
    assert len(context.batch) == 2  # nothing appended the second time
