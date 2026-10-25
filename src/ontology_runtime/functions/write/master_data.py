"""Write functions for master data (outlets, routes)."""

from __future__ import annotations

from typing import Any

from ontology_runtime.actions.context import EditContext
from ontology_runtime.errors import ValidationFailed


def _invalid(path: str, message: str) -> ValidationFailed:
    return ValidationFailed([{"code": "invalid", "path": path, "message": message}])


async def upsert_outlet(context: EditContext, params: dict[str, Any]) -> None:
    outlet_no = params.get("outletNo")
    existing = None
    if outlet_no:
        matches = await context.search(
            "Outlet", {"field": "outletNo", "op": "eq", "value": outlet_no}
        )
        existing = matches[0] if matches else None

    updates: dict[str, Any] = {
        key: params[key]
        for key in ("name", "outletType", "address", "deliveryWeekday", "salesRepRid")
        if key in params and params[key] is not None
    }
    if params.get("depot"):
        updates["depotRid"] = params["depot"]
    if params.get("salesRep"):
        updates["salesRepRid"] = params["salesRep"]

    if existing is not None:
        await context.modify(existing.rid, updates)
        if params.get("depot"):
            context.link("outletDepot", existing.rid, params["depot"])
        if params.get("salesRep"):
            context.link("outletSalesRep", existing.rid, params["salesRep"])
        context.scratch["outletRid"] = existing.rid
        return

    if not outlet_no:
        sequence = len(await context.search("Outlet")) + 1
        outlet_no = f"OUT-{sequence:05d}"
    missing = [k for k in ("name", "outletType") if not params.get(k)]
    if missing:
        raise _invalid(missing[0], f"신규 거래처 등록에는 {missing[0]}가 필요합니다.")

    rid = context.create(
        "Outlet",
        {
            "outletNo": outlet_no,
            "name": params["name"],
            "outletType": params["outletType"],
            "address": params.get("address"),
            "deliveryWeekday": params.get("deliveryWeekday"),
            "depotRid": params.get("depot"),
            "salesRepRid": params.get("salesRep"),
            "status": "active",
        },
    )
    if params.get("depot"):
        context.link("outletDepot", rid, params["depot"])
    if params.get("salesRep"):
        context.link("outletSalesRep", rid, params["salesRep"])
    context.scratch["outletRid"] = rid


async def upsert_delivery_route(context: EditContext, params: dict[str, Any]) -> None:
    route_code = params["routeCode"]
    matches = await context.search(
        "DeliveryRoute", {"field": "routeCode", "op": "eq", "value": route_code}
    )
    fields = {
        "name": params["name"],
        "weekday": int(params["weekday"]),
        "depotRid": params["depot"],
    }
    if params.get("salesRep"):
        fields["salesRepRid"] = params["salesRep"]

    if matches:
        await context.modify(matches[0].rid, fields)
        context.scratch["routeRid"] = matches[0].rid
        return
    rid = context.create(
        "DeliveryRoute",
        {"routeCode": route_code, "active": True, **fields},
    )
    context.link("routeDepot", rid, params["depot"])
    if params.get("salesRep"):
        context.link("routeSalesRep", rid, params["salesRep"])
    context.scratch["routeRid"] = rid
