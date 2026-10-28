"""Deterministic end-to-end walkthrough for the liquor domain, printed as a trace."""

from __future__ import annotations

import datetime as dt
import json

from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.domains.liquor.seed.generator import SeedGenerator
from ontology_runtime.registry import SchemaRegistry
from ontology_runtime.runtime import Runtime

#: A fixed date keeps the trace reproducible across runs.
DEMO_DATE = dt.date(2026, 10, 26)


async def run_demo(registry: SchemaRegistry, session: AsyncSession, *, seed: int = 42) -> int:
    generator = SeedGenerator(registry, session, seed=seed, today=DEMO_DATE)
    await generator.reset()
    await generator.run()
    await session.commit()

    runtime = Runtime(registry, session)
    print("─" * 60)
    print("1) 데이터 현황")
    for name in ("Depot", "Outlet", "Product", "SalesOrder", "Delivery", "SalesInvoice"):
        page = await runtime.sets.search(name, page_size=1)
        print(f"   {name:14} {page.total:5}")

    print("\n2) 배차 대상 확정 발주")
    confirmed = await runtime.sets.search(
        "SalesOrder", filter={"field": "status", "op": "eq", "value": "confirmed"}, page_size=3
    )
    print(f"   확정 발주 {confirmed.total}건 (예시 {len(confirmed.objects)}건)")

    deliveries = await runtime.sets.search("Delivery", page_size=1)
    if deliveries.objects:
        delivery = deliveries.objects[0]
        print("\n3) 배송 건 예시")
        print(
            f"   {delivery.properties['deliveryNo']} · 정류장 {delivery.properties['totalStops']}"
        )

        stops = await runtime.links.targets(registry.link_on("Delivery", "stops"), delivery.rid)
        if stops:
            result = await runtime.validate(
                "CompleteStop", {"stop": stops[0].rid, "actualCases": 1}
            )
            print("\n4) 납품 완료 검증(드라이런)")
            print(f"   status={result.status} obstacles={len(result.violations)}")

    print("\n5) 에이전트 화면")
    for agent in registry.bundle.agents.values():
        print(f"   {agent.apiName:20} 제안가능 {len(agent.allowedActionTypes)}종")
    print("─" * 60)
    print(json.dumps({"ok": True, "seed": seed}, ensure_ascii=False))
    return 0
