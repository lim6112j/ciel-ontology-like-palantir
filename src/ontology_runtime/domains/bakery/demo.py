"""Deterministic end-to-end walkthrough for the bakery domain, printed as a trace."""

from __future__ import annotations

import datetime as dt

from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.domains.bakery.seed.generator import SeedGenerator
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
    for name in ("Product", "Store", "Batch", "ProductionPlan", "Shipment", "StoreStock"):
        page = await runtime.sets.search(name, page_size=1)
        print(f"   {name:15} {page.total:5}")

    print("\n2) 진행 중 생산계획")
    in_progress = await runtime.sets.search(
        "ProductionPlan",
        filter={"field": "status", "op": "eq", "value": "in_progress"},
        page_size=1,
    )
    if not in_progress.objects:
        print("   진행 중 계획이 없습니다. 종료합니다.")
        return 1
    plan = in_progress.objects[0]
    product = await runtime.objects.get(str(plan.properties["productRid"]))
    print(
        f"   {plan.properties['planNo']} · {product.properties['name']}"
        f" · 계획 {plan.properties['plannedQty']}개"
    )

    result = await runtime.validate("CompleteProductionPlan", {"plan": plan.rid, "producedQty": 12})
    print("\n3) 생산 완료 검증(드라이런)")
    print(f"   status={result.status} violations={len(result.violations)}")
    if result.violations:
        for violation in result.violations:
            print(f"   - {violation}")
        return 1

    result = await runtime.apply(
        "CompleteProductionPlan", {"plan": plan.rid, "producedQty": 12}, actor="baker01"
    )
    print(f"\n4) 생산 완료 적용: status={result.status}")
    batches = await runtime.sets.search(
        "Batch", filter={"field": "status", "op": "eq", "value": "baked"}, page_size=10
    )
    print(f"   구운 배치 {batches.total}건")

    summary = await runtime.run_function("productionSummary", {"planDate": DEMO_DATE.isoformat()})
    print("\n5) 생산 현황 요약")
    print(f"   {summary['planDate']} 계획 {summary['count']}건 ({summary['byStatus']})")

    expiring = await runtime.run_function("expiringBatches", {"withinDays": 2})
    print("\n6) 소비기한 임박 배치 (2일)")
    for row in expiring["batches"]:
        print(f"   {row['batchNo']} · 남은 {row['daysLeft']}일 · {row['quantity']}개")

    print("\n완료: 기록은 action_runs/action_edits에 남습니다.")
    return 0
