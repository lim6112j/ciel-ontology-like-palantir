"""Link store: create/delete links and traverse them in either direction."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.db.models import LinkRow, ObjectRow
from ontology_runtime.errors import ConflictError, NotFoundError
from ontology_runtime.registry import LinkView, SchemaRegistry
from ontology_runtime.store.object_store import OntologyObject, _to_object


class LinkStore:
    def __init__(self, registry: SchemaRegistry, session: AsyncSession) -> None:
        self.registry = registry
        self.session = session

    async def create(
        self,
        link_type: str,
        from_rid: str,
        to_rid: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        link = self.registry.link_type(link_type)
        from_row = await self.session.get(ObjectRow, from_rid)
        to_row = await self.session.get(ObjectRow, to_rid)
        if from_row is None or from_row.deleted_at is not None:
            raise NotFoundError(f"object {from_rid!r} not found")
        if to_row is None or to_row.deleted_at is not None:
            raise NotFoundError(f"object {to_rid!r} not found")
        if from_row.object_type != link.fromObjectType:
            raise ConflictError(
                f"link {link_type!r} expects fromObjectType {link.fromObjectType!r}, "
                f"got {from_row.object_type!r}"
            )
        if to_row.object_type != link.toObjectType:
            raise ConflictError(
                f"link {link_type!r} expects toObjectType {link.toObjectType!r}, "
                f"got {to_row.object_type!r}"
            )

        await self._enforce_cardinality(link_type, from_rid, to_rid)

        exists = await self.session.get(LinkRow, (link_type, from_rid, to_rid))
        if exists is not None:
            return
        self.session.add(
            LinkRow(
                link_type=link_type,
                from_rid=from_rid,
                to_rid=to_rid,
                properties=properties or {},
            )
        )
        await self.session.flush()

    async def delete(self, link_type: str, from_rid: str, to_rid: str) -> None:
        await self.session.execute(
            delete(LinkRow)
            .where(LinkRow.link_type == link_type)
            .where(LinkRow.from_rid == from_rid)
            .where(LinkRow.to_rid == to_rid)
        )
        await self.session.flush()

    async def targets(self, view: LinkView, source_rid: str) -> list[OntologyObject]:
        """Objects reachable from `source_rid` via `view`."""
        link = view.link
        if view.is_forward:
            stmt = (
                select(ObjectRow)
                .join(
                    LinkRow,
                    (LinkRow.to_rid == ObjectRow.rid) & (LinkRow.link_type == link.apiName),
                )
                .where(LinkRow.from_rid == source_rid)
            )
        else:
            stmt = (
                select(ObjectRow)
                .join(
                    LinkRow,
                    (LinkRow.from_rid == ObjectRow.rid) & (LinkRow.link_type == link.apiName),
                )
                .where(LinkRow.to_rid == source_rid)
            )
        stmt = stmt.where(ObjectRow.deleted_at.is_(None)).order_by(
            ObjectRow.created_at, ObjectRow.rid
        )
        rows = (await self.session.scalars(stmt)).all()
        return [_to_object(row) for row in rows]

    async def source_rids(self, view: LinkView, source_rid: str) -> list[str]:
        link = view.link
        if view.is_forward:
            stmt = select(LinkRow.to_rid).where(
                LinkRow.link_type == link.apiName, LinkRow.from_rid == source_rid
            )
        else:
            stmt = select(LinkRow.from_rid).where(
                LinkRow.link_type == link.apiName, LinkRow.to_rid == source_rid
            )
        return list((await self.session.scalars(stmt)).all())

    async def count(self, view: LinkView, source_rid: str) -> int:
        return len(await self.source_rids(view, source_rid))

    # -- helpers -----------------------------------------------------------
    async def _enforce_cardinality(self, link_type: str, from_rid: str, to_rid: str) -> None:
        """Enforce declared cardinality.

        `fromCardinality` bounds targets per source; `toCardinality` bounds sources per target.
        """
        link = self.registry.link_type(link_type)
        if link.fromCardinality.value == "one":
            existing = await self.session.scalars(
                select(LinkRow.to_rid)
                .where(LinkRow.link_type == link_type)
                .where(LinkRow.from_rid == from_rid)
            )
            others = [rid for rid in existing.all() if rid != to_rid]
            if others:
                raise ConflictError(
                    f"link {link_type!r} allows one target per source: "
                    f"{from_rid!r} already links to {others[0]!r}"
                )
        if link.toCardinality.value == "one":
            existing = await self.session.scalars(
                select(LinkRow.from_rid)
                .where(LinkRow.link_type == link_type)
                .where(LinkRow.to_rid == to_rid)
            )
            others = [rid for rid in existing.all() if rid != from_rid]
            if others:
                raise ConflictError(
                    f"link {link_type!r} allows one source per target: "
                    f"{to_rid!r} already linked from {others[0]!r}"
                )
