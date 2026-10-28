"""Command line interface, scoped to one business domain.

Every command accepts `--domain <name>` (default: `ONTOLOGY_DOMAIN`, else
`liquor`) so a single checkout can drive several independent domain instances.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import sys
from pathlib import Path
from typing import Any, cast

from ontology_runtime.config import PROJECT_ROOT, list_domain_dirs, settings
from ontology_runtime.registry import SchemaRegistry

#: Domain Python modules the CLI delegates to when present.
_DOMAIN_MODULES = {
    "seed": "seed.generator",
    "demo": "demo",
    "invariants": "invariants",
}


def _split_domain(argv: list[str]) -> tuple[str | None, list[str]]:
    """Pull `--domain X` / `--domain=X` out of argv wherever it appears.

    argparse only accepts a global option before the subcommand, but operators
    naturally type it after. A pre-scan keeps both orders working.
    """
    domain: str | None = None
    rest: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--domain":
            if index + 1 >= len(argv):
                raise SystemExit("ontology: error: --domain requires a value")
            domain = argv[index + 1]
            index += 2
            continue
        if token.startswith("--domain="):
            domain = token.split("=", 1)[1]
            index += 1
            continue
        rest.append(token)
        index += 1
    return domain, rest


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    explicit_domain, argv = _split_domain(argv)

    parser = argparse.ArgumentParser(prog="ontology", description="멀티 도메인 온톨로지 런타임")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("schema", help="스키마 검증").add_argument(
        "action", choices=["validate"], nargs="?", default="validate"
    )
    sub.add_parser("domains", help="도메인 목록과 요약")

    domain = sub.add_parser("domain", help="도메인 상태 점검")
    domain.add_argument("action", choices=["check"], nargs="?", default="check")

    db = sub.add_parser("db", help="데이터베이스 작업")
    db.add_argument("action", choices=["init", "reset"])

    sub.add_parser("sync-indexes", help="선언된 인덱스 동기화")

    seed = sub.add_parser("seed", help="합성 데이터 생성")
    seed.add_argument("--seed", type=int, default=42)
    seed.add_argument("--today", default=None, help="기준일 (YYYY-MM-DD)")

    export = sub.add_parser("export-client", help="TypeScript 클라이언트 생성")
    export.add_argument("--out", default=None, help="기본: apps/web/src/generated/<domain>")

    export_web = sub.add_parser("export-web", help="모든 도메인 클라이언트 + 랜딩 매니페스트 생성")
    export_web.add_argument("--out", default="apps/web/src/generated")

    sub.add_parser("docs", help="docs/domains/<domain>/ontology.md 생성")

    demo = sub.add_parser("demo", help="도메인 시연 (도메인이 제공하는 경우)")
    demo.add_argument("--seed", type=int, default=42)

    args = parser.parse_args(argv)
    domain_name = explicit_domain or settings.domain

    if args.command == "schema":
        return _schema_validate(domain_name)
    if args.command == "domains":
        return _domains()
    if args.command == "domain":
        return asyncio.run(_domain_check(domain_name))
    if args.command == "db":
        return asyncio.run(_db(domain_name, args.action))
    if args.command == "sync-indexes":
        return asyncio.run(_db(domain_name, "init"))
    if args.command == "seed":
        return _seed(domain_name, args.seed, args.today)
    if args.command == "export-client":
        return _export_client(domain_name, args.out)
    if args.command == "export-web":
        return _export_web(args.out)
    if args.command == "docs":
        return _docs(domain_name)
    if args.command == "demo":
        return asyncio.run(_demo(domain_name, args.seed))
    return 1


def _registry(domain: str) -> SchemaRegistry:
    return SchemaRegistry.from_domain(domain)


def _domain_module(domain: str, key: str) -> Any | None:
    """Import a domain-specific implementation module, if the domain ships one."""
    manifest = _registry(domain).domain
    if manifest is None or not manifest.pythonPackage:
        return None
    relative = _DOMAIN_MODULES.get(key)
    if relative is None:
        return None
    try:
        return importlib.import_module(f"{manifest.pythonPackage}.{relative}")
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith(manifest.pythonPackage):
            return None
        raise


def _schema_validate(domain: str) -> int:
    try:
        registry = _registry(domain)
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator
        print(f"❌ 스키마 오류: {exc}", file=sys.stderr)
        return 1
    bundle = registry.bundle
    label = bundle.domain.displayName if bundle.domain else domain
    print(f"✅ 스키마 검증 통과 ({domain}: {label})")
    print(f"   오브젝트 타입 {len(bundle.object_types)}")
    print(f"   링크 타입     {len(bundle.link_types)}")
    print(f"   액션 타입     {len(bundle.action_types)}")
    print(f"   함수          {len(bundle.functions)}")
    print(f"   에이전트      {len(bundle.agents)}")
    print(f"   인덱스        {len(registry.indexes())}")
    return 0


def _domains() -> int:
    directories = list_domain_dirs()
    if not directories:
        print("등록된 도메인이 없습니다.", file=sys.stderr)
        return 1
    print(f"{'도메인':16} {'이름':20} {'타입':>5} {'액션':>5} {'에이전트':>6}")
    for directory in directories:
        name = directory.name
        registry = _registry(name)
        bundle = registry.bundle
        print(
            f"{name:16} {bundle.domain.displayName if bundle.domain else '':20} "
            f"{len(bundle.object_types):5} {len(bundle.action_types):5} "
            f"{len(bundle.agents):6}"
        )
    return 0


async def _domain_check(domain: str) -> int:
    """Fail when the database holds object types this domain does not define."""
    from sqlalchemy import text

    from ontology_runtime.db.engine import get_session_factory

    registry = _registry(domain)
    declared = set(registry.bundle.object_types)
    async with get_session_factory(domain)() as session:
        rows = await session.execute(
            text("SELECT DISTINCT object_type FROM objects WHERE deleted_at IS NULL")
        )
        present = {row[0] for row in rows}

    foreign = present - declared
    if foreign:
        print(
            f"❌ {domain!r} 데이터베이스에 이 도메인에 없는 object_type이 있습니다: "
            f"{', '.join(sorted(foreign))}",
            file=sys.stderr,
        )
        print(
            "   DATABASE_URL을 확인하거나 다른 도메인의 DB를 가리키고 있지 않은지 확인하세요.",
            file=sys.stderr,
        )
        return 1
    print(f"✅ {domain}: 객체 {len(present)}종 모두 이 도메인 정의에 속합니다")
    return 0


async def _db(domain: str, action: str) -> int:
    from sqlalchemy import text

    from ontology_runtime.db.engine import get_session_factory

    if action == "reset":
        async with get_session_factory(domain)() as session:
            await session.execute(
                text(
                    "TRUNCATE objects, links, action_runs, action_edits, agent_runs, "
                    "ontology_indexes RESTART IDENTITY CASCADE"
                )
            )
            await session.commit()
        print(f"✅ {domain} 데이터 초기화 완료")
        return 0

    from ontology_runtime.store.index_sync import IndexSync

    registry = _registry(domain)
    async with get_session_factory(domain)() as session:
        result = await IndexSync(registry, session).sync()
        await session.commit()
    print(f"✅ 인덱스 동기화: 생성 {len(result.created)}, 삭제 {len(result.dropped)}")
    return 0


def _seed(domain: str, seed: int, today: str | None) -> int:
    import datetime as dt

    module = _domain_module(domain, "seed")
    if module is None:
        print(f"ℹ️  {domain} 도메인은 시드 데이터를 제공하지 않습니다.", file=sys.stderr)
        return 0

    from ontology_runtime.db.engine import get_session_factory

    async def run() -> dict[str, int]:
        registry = _registry(domain)
        async with get_session_factory(domain)() as session:
            generator = module.SeedGenerator(
                registry,
                session,
                seed=seed,
                today=dt.date.fromisoformat(today) if today else None,
            )
            await generator.reset()
            summary = await generator.run()
            await session.commit()
        return cast(dict[str, int], summary.to_dict())

    summary = asyncio.run(run())
    print(f"✅ {domain} 합성 데이터 생성 완료")
    for key, value in summary.items():
        print(f"   {key:12} {value}")
    return 0


def _export_client(domain: str, out: str | None) -> int:
    from ontology_runtime.clientgen.generator import write_client

    target = Path(out) if out else _default_client_dir(domain)
    paths = write_client(_registry(domain), target)
    print(f"✅ {domain} TypeScript 클라이언트 생성")
    for path in paths:
        print(f"   {path}")
    return 0


def _default_client_dir(domain: str) -> Path:
    return _web_generated_dir() / domain


def _web_generated_dir() -> Path:
    return PROJECT_ROOT / "apps" / "web" / "src" / "generated"


def _export_web(out: str) -> int:
    from ontology_runtime.clientgen.web import write_web_bundle

    paths = write_web_bundle(Path(out))
    print("✅ 웹 번들 생성")
    for path in paths:
        print(f"   {path}")
    return 0


def _docs(domain: str) -> int:
    from ontology_runtime.clientgen.generator import render_ontology_markdown

    target = PROJECT_ROOT / "docs" / "domains" / domain / "ontology.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_ontology_markdown(_registry(domain)), encoding="utf-8")
    print(f"✅ {target}")
    return 0


async def _demo(domain: str, seed: int) -> int:
    module = _domain_module(domain, "demo")
    if module is None:
        print(f"ℹ️  {domain} 도메인은 데모를 제공하지 않습니다.", file=sys.stderr)
        return 0

    from ontology_runtime.db.engine import get_session_factory

    registry = _registry(domain)
    async with get_session_factory(domain)() as session:
        return cast(int, await module.run_demo(registry, session, seed=seed))


if __name__ == "__main__":
    raise SystemExit(main())
