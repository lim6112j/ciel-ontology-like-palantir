"""Command line interface: schema validate, db init, indexes, seed, export, demo."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from ontology_runtime.config import PROJECT_ROOT, SCHEMA_DIR
from ontology_runtime.registry import SchemaRegistry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ontology", description="주류 도매 온톨로지 런타임")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("schema", help="스키마 검증").add_argument(
        "action", choices=["validate"], nargs="?", default="validate"
    )

    db = sub.add_parser("db", help="데이터베이스 작업")
    db.add_argument("action", choices=["init", "reset"])

    sub.add_parser("sync-indexes", help="선언된 인덱스 동기화")

    seed = sub.add_parser("seed", help="합성 데이터 생성")
    seed.add_argument("--seed", type=int, default=42)
    seed.add_argument("--today", default=None, help="기준일 (YYYY-MM-DD)")

    export = sub.add_parser("export-client", help="TypeScript 클라이언트 생성")
    export.add_argument("--out", default="apps/web/src/generated")

    sub.add_parser("docs", help="docs/ontology.md 생성")

    demo = sub.add_parser("demo", help="발주→배차→납품 시연")
    demo.add_argument("--seed", type=int, default=42)

    args = parser.parse_args(argv)

    if args.command == "schema":
        return _schema_validate()
    if args.command == "db":
        return asyncio.run(_db(args.action))
    if args.command == "sync-indexes":
        return asyncio.run(_db("init"))
    if args.command == "seed":
        return _seed(args.seed, args.today)
    if args.command == "export-client":
        return _export_client(args.out)
    if args.command == "docs":
        return _docs()
    if args.command == "demo":
        return asyncio.run(_demo(args.seed))
    return 1


def _registry() -> SchemaRegistry:
    return SchemaRegistry.from_directory(SCHEMA_DIR)


def _schema_validate() -> int:
    try:
        registry = _registry()
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator
        print(f"❌ 스키마 오류: {exc}", file=sys.stderr)
        return 1
    bundle = registry.bundle
    print("✅ 스키마 검증 통과")
    print(f"   오브젝트 타입 {len(bundle.object_types)}")
    print(f"   링크 타입     {len(bundle.link_types)}")
    print(f"   액션 타입     {len(bundle.action_types)}")
    print(f"   함수          {len(bundle.functions)}")
    print(f"   에이전트      {len(bundle.agents)}")
    print(f"   인덱스        {len(registry.indexes())}")
    return 0


async def _db(action: str) -> int:
    from sqlalchemy import text

    from ontology_runtime.db.engine import get_session_factory

    if action == "reset":
        async with get_session_factory()() as session:
            await session.execute(
                text(
                    "TRUNCATE objects, links, action_runs, action_edits, agent_runs, "
                    "ontology_indexes RESTART IDENTITY CASCADE"
                )
            )
            await session.commit()
        print("✅ 데이터 초기화 완료")
        return 0

    from ontology_runtime.store.index_sync import IndexSync

    registry = _registry()
    async with get_session_factory()() as session:
        result = await IndexSync(registry, session).sync()
        await session.commit()
    print(f"✅ 인덱스 동기화: 생성 {len(result.created)}, 삭제 {len(result.dropped)}")
    return 0


def _seed(seed: int, today: str | None) -> int:
    import datetime as dt

    from ontology_runtime.db.engine import get_session_factory
    from ontology_runtime.seed.generator import SeedGenerator

    async def run() -> dict[str, int]:
        registry = _registry()
        async with get_session_factory()() as session:
            generator = SeedGenerator(
                registry,
                session,
                seed=seed,
                today=dt.date.fromisoformat(today) if today else None,
            )
            await generator.reset()
            summary = await generator.run()
            await session.commit()
        return summary.to_dict()

    summary = asyncio.run(run())
    print("✅ 합성 데이터 생성 완료")
    for key, value in summary.items():
        print(f"   {key:12} {value}")
    return 0


def _export_client(out: str) -> int:
    from ontology_runtime.clientgen.generator import write_client

    paths = write_client(_registry(), Path(out))
    print("✅ TypeScript 클라이언트 생성")
    for path in paths:
        print(f"   {path}")
    return 0


def _docs() -> int:
    from ontology_runtime.clientgen.generator import render_ontology_markdown

    target = PROJECT_ROOT / "docs" / "ontology.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_ontology_markdown(_registry()), encoding="utf-8")
    print(f"✅ {target}")
    return 0


async def _demo(seed: int) -> int:
    """Deterministic end-to-end walkthrough printed as a trace."""
    import datetime as dt

    from ontology_runtime.db.engine import get_session_factory
    from ontology_runtime.runtime import Runtime
    from ontology_runtime.seed.generator import SeedGenerator

    registry = _registry()
    today = dt.date(2026, 10, 26)
    async with get_session_factory()() as session:
        generator = SeedGenerator(registry, session, seed=seed, today=today)
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
                f"   {delivery.properties['deliveryNo']} · "
                f"정류장 {delivery.properties['totalStops']}"
            )

            stops = await runtime.links.targets(registry.link_on("Delivery", "stops"), delivery.rid)
            if stops:
                stop = stops[0]
                result = await runtime.validate(
                    "CompleteStop", {"stop": stop.rid, "actualCases": 1}
                )
                print("\n4) 납품 완료 검증(드라이런)")
                print(f"   status={result.status} obstacles={len(result.violations)}")

        print("\n5) 에이전트 화면")
        for agent in registry.bundle.agents.values():
            print(f"   {agent.apiName:20} 제안가능 {len(agent.allowedActionTypes)}종")
        print("─" * 60)
        print(json.dumps({"ok": True, "seed": seed}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
