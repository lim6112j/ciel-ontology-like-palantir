"""Create declared ontology indexes and drop stale ones."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.db.models import OntologyIndexRow
from ontology_runtime.registry import ResolvedIndex, SchemaRegistry


@dataclass
class SyncResult:
    created: list[str]
    dropped: list[str]

    def as_dict(self) -> dict[str, list[str]]:
        return {"created": self.created, "dropped": self.dropped}


class IndexSync:
    def __init__(self, registry: SchemaRegistry, session: AsyncSession) -> None:
        self.registry = registry
        self.session = session

    async def sync(self) -> SyncResult:
        """Reconcile database indexes with the schema.

        An index is recreated only when its DDL changed, so this is idempotent.
        """
        wanted: dict[str, ResolvedIndex] = {spec.name: spec for spec in self.registry.indexes()}
        recorded = {
            row.name: row for row in (await self.session.scalars(select(OntologyIndexRow))).all()
        }

        created: list[str] = []
        dropped: list[str] = []
        for name, row in recorded.items():
            if name not in wanted:
                await self.session.execute(text(f"DROP INDEX IF EXISTS {name}"))
                await self.session.delete(row)
                dropped.append(name)

        for name, spec in wanted.items():
            ddl = spec.ddl()
            existing = recorded.get(name)
            if existing is not None and existing.ddl == ddl:
                continue
            await self.session.execute(text(f"DROP INDEX IF EXISTS {name}"))
            await self.session.execute(text(ddl))
            if existing is not None:
                existing.ddl = ddl
                existing.schema_hash = self.registry.bundle.schema_hash()
            else:
                self.session.add(
                    OntologyIndexRow(
                        name=name,
                        object_type=spec.object_type,
                        ddl=ddl,
                        schema_hash=self.registry.bundle.schema_hash(),
                    )
                )
            created.append(name)

        await self.session.flush()
        return SyncResult(created=created, dropped=dropped)
