"""Object set service: search, order, paginate, aggregate, and traverse links."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Select, asc, desc, func, select
from sqlalchemy import cast as sa_cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import Numeric

from ontology_runtime.db.models import ObjectRow
from ontology_runtime.errors import ValidationFailed
from ontology_runtime.meta import PropertyType
from ontology_runtime.query.filter import _SQL_TYPE, compile_filter
from ontology_runtime.registry import LinkView, SchemaRegistry
from ontology_runtime.store.object_store import OntologyObject, _to_object

MAX_PAGE_SIZE = 500
DEFAULT_PAGE_SIZE = 50


@dataclass
class OrderBy:
    field: str
    direction: str = "asc"


@dataclass
class Page:
    objects: list[OntologyObject]
    total: int
    page_size: int
    page_token: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "data": [obj.to_dict() for obj in self.objects],
            "meta": {
                "total": self.total,
                "pageSize": self.page_size,
                "pageToken": self.page_token,
                "nextPageToken": (
                    self.page_token + 1
                    if (self.page_token + 1) * self.page_size < self.total
                    else None
                ),
            },
        }


@dataclass
class AggregateSpec:
    groupBy: list[str] = field(default_factory=list)
    select: list[dict[str, Any]] = field(default_factory=list)
    filter: Any = None


class ObjectSetService:
    def __init__(self, registry: SchemaRegistry, session: AsyncSession) -> None:
        self.registry = registry
        self.session = session

    # -- search ------------------------------------------------------------
    async def search(
        self,
        object_type: str,
        *,
        filter: Any = None,
        order_by: list[OrderBy] | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        page_token: int = 0,
        select_properties: list[str] | None = None,
    ) -> Page:
        obj_def = self.registry.object_type(object_type)
        page_size = max(1, min(page_size, MAX_PAGE_SIZE))
        page_token = max(0, page_token)

        base = select(ObjectRow).where(ObjectRow.object_type == object_type)
        base = base.where(ObjectRow.deleted_at.is_(None))

        expression = compile_filter(object_type, obj_def.properties, filter) if filter else None
        if expression is not None:
            base = base.where(expression)

        total = await self.session.scalar(select(func.count()).select_from(base.subquery())) or 0

        stmt = self._apply_order(base, object_type, order_by)
        stmt = stmt.offset(page_token * page_size).limit(page_size)
        rows = (await self.session.scalars(stmt)).all()

        objects = [_to_object(row) for row in rows]
        if select_properties:
            unknown = set(select_properties) - set(obj_def.properties)
            if unknown:
                raise ValidationFailed(
                    [
                        {
                            "code": "unknown_property",
                            "path": "select",
                            "message": f"{object_type} has no property {sorted(unknown)[0]!r}",
                        }
                    ]
                )
            objects = [
                OntologyObject(
                    rid=obj.rid,
                    object_type=obj.object_type,
                    properties={k: v for k, v in obj.properties.items() if k in select_properties},
                    version=obj.version,
                    created_at=obj.created_at,
                    updated_at=obj.updated_at,
                )
                for obj in objects
            ]
        return Page(objects=objects, total=total, page_size=page_size, page_token=page_token)

    async def count(self, object_type: str, filter: Any = None) -> int:
        obj_def = self.registry.object_type(object_type)
        stmt = (
            select(func.count())
            .select_from(ObjectRow)
            .where(ObjectRow.object_type == object_type, ObjectRow.deleted_at.is_(None))
        )
        expression = compile_filter(object_type, obj_def.properties, filter) if filter else None
        if expression is not None:
            stmt = stmt.where(expression)
        return await self.session.scalar(stmt) or 0

    # -- aggregation -------------------------------------------------------
    async def aggregate(self, object_type: str, spec: AggregateSpec) -> list[dict[str, Any]]:
        obj_def = self.registry.object_type(object_type)
        violations: list[dict[str, Any]] = []

        for name in spec.groupBy:
            if name not in obj_def.properties:
                violations.append(
                    {
                        "code": "unknown_property",
                        "path": "groupBy",
                        "message": f"{object_type} has no property {name!r}",
                    }
                )
        for entry in spec.select:
            field_name = entry.get("field")
            if field_name and field_name not in obj_def.properties:
                violations.append(
                    {
                        "code": "unknown_property",
                        "path": "select.field",
                        "message": f"{object_type} has no property {field_name!r}",
                    }
                )
        if violations:
            raise ValidationFailed(violations)

        group_columns = [self._typed_column(object_type, name).label(name) for name in spec.groupBy]
        agg_columns = []
        for entry in spec.select:
            operation = entry.get("op", "count")
            alias = entry.get("as") or f"{operation}_{entry.get('field') or 'all'}"
            target = (
                func.count()
                if operation == "count" and not entry.get("field")
                else func.count(self._typed_column(object_type, entry["field"]))
            )
            if operation in {"sum", "avg", "min", "max"}:
                column = self._typed_column(object_type, entry["field"])
                prop = obj_def.properties[entry["field"]]
                if prop.type not in (
                    PropertyType.INTEGER,
                    PropertyType.BIGINT,
                    PropertyType.DECIMAL,
                ):
                    raise ValidationFailed(
                        [
                            {
                                "code": "invalid_aggregate",
                                "path": "select",
                                "message": f"{operation!r} requires a numeric property",
                            }
                        ]
                    )
                aggregate_fns: dict[str, Callable[..., Any]] = {
                    "sum": func.sum,
                    "avg": func.avg,
                    "min": func.min,
                    "max": func.max,
                }
                target = aggregate_fns[operation](column)
            agg_columns.append(target.label(alias))

        stmt: Select[Any] = select(*group_columns, *agg_columns).select_from(ObjectRow)
        stmt = stmt.where(ObjectRow.object_type == object_type, ObjectRow.deleted_at.is_(None))
        expression = (
            compile_filter(object_type, obj_def.properties, spec.filter) if spec.filter else None
        )
        if expression is not None:
            stmt = stmt.where(expression)
        if group_columns:
            stmt = stmt.group_by(*group_columns)
            stmt = stmt.order_by(*group_columns)

        rows = (await self.session.execute(stmt)).all()
        return [dict(row._mapping) for row in rows]

    # -- link traversal ----------------------------------------------------
    async def search_around(
        self,
        source_rid: str,
        link_name: str,
        *,
        filter: Any = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        page_token: int = 0,
    ) -> Page:
        source = await self.session.get(ObjectRow, source_rid)
        if source is None or source.deleted_at is not None:
            from ontology_runtime.errors import NotFoundError

            raise NotFoundError(f"object {source_rid!r} not found")
        view: LinkView = self.registry.link_on(source.object_type, link_name)
        from ontology_runtime.store.link_store import LinkStore

        targets = await LinkStore(self.registry, self.session).targets(view, source_rid)
        if filter:
            obj_def = self.registry.object_type(view.target_type)
            expression = compile_filter(view.target_type, obj_def.properties, filter)
            if expression is not None:
                total_subq = select(ObjectRow.rid).where(
                    ObjectRow.object_type == view.target_type,
                    ObjectRow.deleted_at.is_(None),
                    expression,
                )
                allowed = set((await self.session.scalars(total_subq)).all())
                targets = [obj for obj in targets if obj.rid in allowed]
        total = len(targets)
        start = page_token * page_size
        return Page(
            objects=targets[start : start + page_size],
            total=total,
            page_size=page_size,
            page_token=page_token,
        )

    # -- helpers -----------------------------------------------------------
    def _apply_order(
        self, stmt: Select[Any], object_type: str, order_by: list[OrderBy] | None
    ) -> Select[Any]:
        if not order_by:
            return stmt.order_by(asc(ObjectRow.created_at), asc(ObjectRow.rid))
        obj_def = self.registry.object_type(object_type)
        violations = []
        clauses = []
        for entry in order_by:
            if entry.field not in obj_def.properties:
                violations.append(
                    {
                        "code": "unknown_property",
                        "path": "orderBy.field",
                        "message": f"{object_type} has no property {entry.field!r}",
                    }
                )
                continue
            if entry.direction not in ("asc", "desc"):
                violations.append(
                    {
                        "code": "invalid_order",
                        "path": "orderBy.direction",
                        "message": f"direction must be 'asc' or 'desc', got {entry.direction!r}",
                    }
                )
                continue
            column = self._typed_column(object_type, entry.field)
            clauses.append(desc(column) if entry.direction == "desc" else asc(column))
        if violations:
            raise ValidationFailed(violations)
        if not clauses:
            return stmt.order_by(asc(ObjectRow.rid))
        return stmt.order_by(*clauses, asc(ObjectRow.rid))

    def _typed_column(self, object_type: str, property_name: str) -> Any:
        prop = self.registry.object_type(object_type).properties[property_name]
        raw = ObjectRow.properties.op("->>")(property_name)
        sql_type = _SQL_TYPE.get(prop.type) or Numeric
        return sa_cast(raw, sql_type)


def parse_order_by(raw: Any) -> list[OrderBy]:
    """Accept either `[{"field","direction"}]` or `{"field": "asc|desc"}`."""
    if not raw:
        return []
    if isinstance(raw, dict):
        return [OrderBy(field=name, direction=direction) for name, direction in raw.items()]
    if isinstance(raw, list):
        return [
            OrderBy(field=entry.get("field", ""), direction=entry.get("direction", "asc"))
            for entry in raw
        ]
    return []
