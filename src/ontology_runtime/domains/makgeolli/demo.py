"""Deterministic end-to-end walkthrough for the makgeolli domain, printed as a trace."""

from __future__ import annotations

import datetime as dt

from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.domains.makgeolli.seed.generator import SeedGenerator
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
    for name in (
        "Product",
        "Customer",
        "Tank",
        "Batch",
        "SalesOrder",
        "Shipment",
        "WarehouseStock",
        "TempReading",
    ):
        page = await runtime.sets.search(name, page_size=1)
        print(f"   {name:15} {page.total:5}")

    pipeline = await runtime.run_function("productionPipeline", {})
    print("\n2) 양조 파이프라인")
    for row in pipeline["batches"]:
        overdue = f" · 지연 {row['daysOverdue']}일" if row["daysOverdue"] else ""
        print(
            f"   {row['batchNo']} · {row['product']} · {row['status']} · "
            f"{row['stage']} {row['progressPercent']}%{overdue}"
        )

    deviations = await runtime.run_function("tempDeviations", {"withinDays": 7})
    print("\n3) 온도 이탈")
    for row in deviations["readings"]:
        print(
            f"   {row['batchNo']} · {row['stage']} · 측정 {row['tempC']}°C / "
            f"목표 {row['targetTempC']}°C"
        )
    if not deviations["readings"]:
        print("   이탈 없음")

    batch_page = await runtime.sets.search(
        "Batch", filter={"field": "status", "op": "eq", "value": "aging"}, page_size=1
    )
    if not batch_page.objects:
        print("   병입 대상 배치가 없습니다. 종료합니다.")
        return 1
    batch = batch_page.objects[0]

    result = await runtime.validate("CompleteAging", {"batch": batch.rid})
    print("\n4) 숙성 완료·병입 검증(드라이런)")
    print(f"   status={result.status} violations={len(result.violations)}")
    if result.violations:
        for violation in result.violations:
            print(f"   - {violation}")
        return 1

    result = await runtime.apply("CompleteAging", {"batch": batch.rid}, actor="brewer01")
    print(f"\n5) 숙성 완료 적용: status={result.status}")

    expiring = await runtime.run_function("expiringBatches", {"withinDays": 7})
    print("\n6) 소비기한 임박 배치 (7일)")
    for row in expiring["batches"]:
        print(f"   {row['batchNo']} · 남은 {row['daysLeft']}일 · {row['bottledQty']}병")

    print("\n완료: 기록은 action_runs/action_edits에 남습니다.")
    return 0
