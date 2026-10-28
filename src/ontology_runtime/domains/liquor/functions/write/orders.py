"""Write functions for the order lifecycle."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from ontology_runtime.actions.context import EditContext

VAT_TAX_TYPE = "과세"
TAX_RATE_NUMERATOR = 10
TAX_RATE_DENOMINATOR = 100
DRAFT_STATUS = "draft"


@dataclass
class _ResolvedLine:
    product: Any
    cases: int
    unit_price: int

    @property
    def amount(self) -> int:
        return self.unit_price * self.cases


async def create_sales_order(context: EditContext, params: dict[str, Any]) -> None:
    outlet_rid = params["outlet"]
    outlet = await context.require(outlet_rid)
    if outlet.properties.get("status") != "active":
        raise _invalid(
            "outlet", f"{outlet.properties.get('name')}는 현재 주문할 수 없는 상태입니다."
        )

    raw_lines = params.get("lines") or []
    if not raw_lines:
        raise _invalid("lines", "최소 한 개의 발주 라인이 필요합니다.")

    order_no = await _next_order_no(context, params["orderDate"])
    resolved_lines = []
    for index, raw in enumerate(raw_lines):
        product_rid = raw.get("productRid") or raw.get("product")
        cases = int(raw.get("cases") or 0)
        if not product_rid:
            raise _invalid(f"lines[{index}].productRid", "제품 rid가 필요합니다.")
        product = await context.require(product_rid)
        if not product.properties.get("active", True):
            raise _invalid(
                f"lines[{index}].productRid",
                f"{product.properties.get('name')}는 판매 중지 상태입니다.",
            )
        if cases < 1:
            raise _invalid(f"lines[{index}].cases", "케이스는 1 이상이어야 합니다.")
        case_price = int(product.properties.get("casePrice") or 0)
        resolved_lines.append(_ResolvedLine(product=product, cases=cases, unit_price=case_price))

    subtotal = sum(line.amount for line in resolved_lines)
    taxable = sum(
        line.amount
        for line in resolved_lines
        if line.product.properties.get("taxType") == VAT_TAX_TYPE
    )
    tax = taxable * TAX_RATE_NUMERATOR // TAX_RATE_DENOMINATOR
    total_cases = sum(line.cases for line in resolved_lines)

    order_rid = context.create(
        "SalesOrder",
        {
            "orderNo": order_no,
            "outletRid": outlet_rid,
            "salesRepRid": params.get("salesRep") or outlet.properties.get("salesRepRid"),
            "orderDate": params["orderDate"],
            "requestedDeliveryDate": params.get("requestedDeliveryDate"),
            "channel": params.get("channel") or "phone",
            "status": DRAFT_STATUS,
            "totalAmount": subtotal,
            "taxAmount": tax,
            "totalCases": total_cases,
            "note": params.get("note"),
        },
    )

    for index, line in enumerate(resolved_lines, start=1):
        line_rid = context.create(
            "SalesOrderLine",
            {
                "lineNo": f"{order_no}-{index:02d}",
                "orderedCases": line.cases,
                "unitPrice": line.unit_price,
                "lineAmount": line.amount,
                "productName": line.product.properties.get("name", ""),
                "productRid": line.product.rid,
            },
        )
        context.link("orderLines", order_rid, line_rid)
        context.scratch[f"orderLineParent:{line_rid}"] = order_rid

    context.scratch["createdOrderRid"] = order_rid
    context.scratch["createdOrderNo"] = order_no


async def add_order_line(context: EditContext, params: dict[str, Any]) -> None:
    order = await context.require(params["order"])
    if order.properties.get("status") != DRAFT_STATUS:
        raise _invalid("order", "초안 상태의 발주만 수정할 수 있습니다.")
    product = await context.require(params["product"])
    if not product.properties.get("active", True):
        raise _invalid("product", f"{product.properties.get('name')}는 판매 중지 상태입니다.")

    cases = int(params["cases"])
    case_price = int(product.properties.get("casePrice") or 0)
    order_no = order.properties.get("orderNo", "")
    existing = await context.linked(order.rid, "lines")
    line_rid = context.create(
        "SalesOrderLine",
        {
            "lineNo": f"{order_no}-{len(existing) + 1:02d}",
            "orderedCases": cases,
            "unitPrice": case_price,
            "lineAmount": case_price * cases,
            "productName": product.properties.get("name", ""),
            "productRid": product.rid,
        },
    )
    context.link("orderLines", order.rid, line_rid)
    context.scratch[f"orderLineParent:{line_rid}"] = order.rid
    await _recalculate_order(context, order.rid, [*existing, await context.require(line_rid)])


async def remove_order_line(context: EditContext, params: dict[str, Any]) -> None:
    line = await context.require(params["line"])
    parent_rid = await _parent_of_line(context, line.rid)
    if parent_rid is None:
        raise _invalid("line", "발주 라인의 상위 발주를 찾을 수 없습니다.")
    order = await context.require(parent_rid)
    if order.properties.get("status") != DRAFT_STATUS:
        raise _invalid("line", "초안 상태의 발주만 수정할 수 있습니다.")

    remaining = [o for o in await context.linked(order.rid, "lines") if o.rid != line.rid]
    context.unlink("orderLines", order.rid, line.rid)
    await context.delete(line.rid)
    await _recalculate_order(context, order.rid, remaining)


async def _recalculate_order(context: EditContext, order_rid: str, lines: list[Any]) -> None:
    subtotal = sum(int(line.properties.get("lineAmount") or 0) for line in lines)
    total_cases = sum(int(line.properties.get("orderedCases") or 0) for line in lines)
    taxable = 0
    for line in lines:
        product_rid = line.properties.get("productRid")
        product = await context.get(product_rid) if product_rid else None
        if product is None or product.properties.get("taxType") == VAT_TAX_TYPE:
            taxable += int(line.properties.get("lineAmount") or 0)
    await context.modify(
        order_rid,
        {
            "totalAmount": subtotal,
            "taxAmount": taxable * TAX_RATE_NUMERATOR // TAX_RATE_DENOMINATOR,
            "totalCases": total_cases,
        },
    )


async def _parent_of_line(context: EditContext, line_rid: str) -> str | None:
    for order in await context.search("SalesOrder"):
        for linked in await context.linked(order.rid, "lines"):
            if linked.rid == line_rid:
                return order.rid
    return None


async def _next_order_no(context: EditContext, order_date: str) -> str:
    prefix = f"SO-{str(order_date).replace('-', '')}"
    existing = await context.search(
        "SalesOrder", {"field": "orderNo", "op": "startswith", "value": prefix}
    )
    return f"{prefix}-{len(existing) + 1:04d}"


class _Invalid(ValueError):
    def __init__(self, path: str, message: str) -> None:
        super().__init__(message)
        self.path = path


def _invalid(path: str, message: str) -> Exception:
    from ontology_runtime.errors import ValidationFailed

    return ValidationFailed([{"code": "invalid", "path": path, "message": message}])


def _now_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()
