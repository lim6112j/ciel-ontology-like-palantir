"""Read-only order functions: line validation and integer money math."""

from __future__ import annotations

from typing import Any

from ontology_runtime.actions.context import EditContext

TAX_RATE_NUMERATOR = 10
TAX_RATE_DENOMINATOR = 100
MIN_ORDER_CASES = 1
VAT_TAX_TYPE = "과세"


async def compute_order_totals(
    context: EditContext, orderLines: list[str] | None = None
) -> dict[str, Any]:
    """Sum line amounts and cases; tax is 10% of the taxable subtotal."""
    line_rids = orderLines or []
    lines = []
    for rid in line_rids:
        obj = await context.get(rid)
        if obj is not None:
            lines.append(obj)

    subtotal = sum(int(line.properties.get("lineAmount") or 0) for line in lines)
    total_cases = sum(int(line.properties.get("orderedCases") or 0) for line in lines)

    taxable_subtotal = 0
    for line in lines:
        product_rid = line.properties.get("productRid")
        product = await context.get(product_rid) if product_rid else None
        if product is None or product.properties.get("taxType") == VAT_TAX_TYPE:
            taxable_subtotal += int(line.properties.get("lineAmount") or 0)

    tax = taxable_subtotal * TAX_RATE_NUMERATOR // TAX_RATE_DENOMINATOR
    return {
        "subtotal": subtotal,
        "tax": tax,
        "total": subtotal + tax,
        "totalCases": total_cases,
        "lineCount": len(lines),
    }


async def validate_order_line(context: EditContext, product: str, cases: int) -> dict[str, Any]:
    """Check the product is sellable and the quantity is sane."""
    issues: list[dict[str, Any]] = []
    obj = await context.get(product)
    if obj is None:
        issues.append(
            {"code": "product_not_found", "path": "product", "message": "제품을 찾을 수 없습니다."}
        )
        return {"valid": False, "violations": issues}

    if not obj.properties.get("active", True):
        issues.append(
            {
                "code": "product_inactive",
                "path": "product",
                "message": f"{obj.properties.get('name')}는 판매 중지된 제품입니다.",
            }
        )
    if cases < MIN_ORDER_CASES:
        issues.append(
            {
                "code": "below_minimum",
                "path": "cases",
                "message": f"최소 주문 수량은 {MIN_ORDER_CASES}케이스입니다.",
            }
        )
    return {"valid": not issues, "violations": issues}


async def find_area_price_rule(context: EditContext, product: str, outlet: str) -> dict[str, Any]:
    """Resolve the case price for a product at an outlet (list price in v1)."""
    product_obj = await context.get(product)
    outlet_obj = await context.get(outlet)
    if product_obj is None:
        return {"casePrice": 0, "source": "missing_product"}
    if outlet_obj is None:
        return {
            "casePrice": int(product_obj.properties.get("casePrice") or 0),
            "source": "missing_outlet",
        }

    case_price = int(product_obj.properties.get("casePrice") or 0)
    return {
        "casePrice": case_price,
        "productName": product_obj.properties.get("name"),
        "outletType": outlet_obj.properties.get("outletType"),
        "source": "list_price",
    }
