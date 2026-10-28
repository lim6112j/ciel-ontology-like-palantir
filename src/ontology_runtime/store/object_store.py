"""Generic JSONB object store: validation, identity, versioning, soft delete."""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import literal, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.db.models import ObjectRow
from ontology_runtime.errors import NotFoundError, VersionConflict
from ontology_runtime.meta import ObjectTypeDef
from ontology_runtime.registry import SchemaRegistry


@dataclass
class OntologyObject:
    """A materialized object: identity, type, properties, and version."""

    rid: str
    object_type: str
    properties: dict[str, Any]
    version: int = 1
    created_at: dt.datetime | None = None
    updated_at: dt.datetime | None = None
    deleted_at: dt.datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rid": self.rid,
            "objectType": self.object_type,
            "properties": self.properties,
            "version": self.version,
            "createdAt": _iso(self.created_at),
            "updatedAt": _iso(self.updated_at),
        }

    def property(self, api_name: str) -> Any:
        return self.properties.get(api_name)


@dataclass
class ValidationReport:
    violations: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations

    def add(self, code: str, path: str, message: str, **extra: Any) -> None:
        self.violations.append({"code": code, "path": path, "message": message, **extra})


def new_rid(object_type: str, namespace: str) -> str:
    """Mint an object rid: `ri.<namespace>.object.<type>.<id>`.

    The namespace is supplied by the registry (from `domain.yaml`), never read
    from a global setting, so two domains cannot stamp the same prefix.
    """
    return f"ri.{namespace}.object.{object_type.lower()}.{uuid.uuid4().hex[:24]}"


def _iso(value: dt.datetime | None) -> str | None:
    return value.isoformat() if value else None


class ObjectStore:
    def __init__(self, registry: SchemaRegistry, session: AsyncSession) -> None:
        self.registry = registry
        self.session = session

    # -- validation --------------------------------------------------------
    def validate_properties(
        self,
        object_type: str,
        properties: dict[str, Any],
        *,
        partial: bool,
    ) -> tuple[dict[str, Any], ValidationReport]:
        """Coerce and validate properties. Unknown keys are rejected."""
        obj_def = self.registry.object_type(object_type)
        report = ValidationReport()
        coerced: dict[str, Any] = {}

        unknown = set(properties) - set(obj_def.properties)
        for name in sorted(unknown):
            report.add("unknown_property", name, f"{object_type} has no property {name!r}")

        source = dict(properties)
        if not partial:
            for name, prop in obj_def.properties.items():
                if name not in source and prop.defaultValue is not None:
                    source[name] = prop.defaultValue

        for name, prop in obj_def.properties.items():
            if partial and name not in source:
                continue
            raw = source.get(name)
            try:
                value = prop.coerce(raw)
            except ValueError as exc:
                report.add("invalid_property", name, str(exc))
                continue
            coerced[name] = value

        if not partial:
            coerced = {k: v for k, v in coerced.items() if v is not None or _required(obj_def, k)}
        return coerced, report

    # -- reads -------------------------------------------------------------
    async def get(self, rid: str, *, include_deleted: bool = False) -> OntologyObject:
        obj = await self.maybe_get(rid, include_deleted=include_deleted)
        if obj is None:
            raise NotFoundError(f"object {rid!r} not found")
        return obj

    async def maybe_get(self, rid: str, *, include_deleted: bool = False) -> OntologyObject | None:
        # Always read current database state: an action run may follow another run's
        # writes in the same session, and the identity map would otherwise return a stale row.
        row = await self.session.get(ObjectRow, rid, populate_existing=True, with_for_update=False)
        if row is None or (row.deleted_at is not None and not include_deleted):
            return None
        return _to_object(row)

    async def get_many(
        self, rids: list[str], *, include_deleted: bool = False
    ) -> list[OntologyObject]:
        if not rids:
            return []
        stmt = select(ObjectRow).where(ObjectRow.rid.in_(rids))
        if not include_deleted:
            stmt = stmt.where(ObjectRow.deleted_at.is_(None))
        rows = (await self.session.scalars(stmt)).all()
        by_rid = {row.rid: _to_object(row) for row in rows}
        return [by_rid[rid] for rid in rids if rid in by_rid]

    # -- writes ------------------------------------------------------------
    async def create(
        self,
        object_type: str,
        properties: dict[str, Any],
        *,
        rid: str | None = None,
    ) -> OntologyObject:
        obj_def = self.registry.object_type(object_type)
        coerced, report = self.validate_properties(object_type, properties, partial=False)
        if not report.ok:
            from ontology_runtime.errors import ValidationFailed

            raise ValidationFailed(report.violations)

        rid = rid or new_rid(object_type, self.registry.namespace)
        row = ObjectRow(rid=rid, object_type=object_type, properties=coerced, version=1)
        self.session.add(row)
        await self.session.flush()
        await self._check_unique(obj_def, coerced, exclude_rid=rid)
        return _to_object(row)

    async def update(
        self,
        rid: str,
        properties: dict[str, Any],
        *,
        expected_version: int | None = None,
    ) -> OntologyObject:
        row = await self.session.get(ObjectRow, rid, with_for_update=True)
        if row is None or row.deleted_at is not None:
            raise NotFoundError(f"object {rid!r} not found")
        if expected_version is not None and row.version != expected_version:
            raise VersionConflict(
                f"object {rid!r} is at version {row.version}, expected {expected_version}"
            )
        obj_def = self.registry.object_type(row.object_type)
        coerced, report = self.validate_properties(row.object_type, properties, partial=True)
        if not report.ok:
            from ontology_runtime.errors import ValidationFailed

            raise ValidationFailed(report.violations)

        merged = {**row.properties, **coerced}
        for name, value in list(merged.items()):
            prop = obj_def.properties.get(name)
            if prop and value is None and not prop.required:
                merged.pop(name)

        await self._check_unique(obj_def, merged, exclude_rid=rid)
        row.properties = merged
        row.version = row.version + 1
        row.updated_at = dt.datetime.now(dt.UTC)
        await self.session.flush()
        return _to_object(row)

    async def soft_delete(self, rid: str, *, expected_version: int | None = None) -> None:
        row = await self.session.get(ObjectRow, rid, with_for_update=True)
        if row is None or row.deleted_at is not None:
            raise NotFoundError(f"object {rid!r} not found")
        if expected_version is not None and row.version != expected_version:
            raise VersionConflict(
                f"object {rid!r} is at version {row.version}, expected {expected_version}"
            )
        row.deleted_at = dt.datetime.now(dt.UTC)
        row.version = row.version + 1
        await self.session.flush()

    async def restore(self, rid: str) -> OntologyObject:
        row = await self.session.get(ObjectRow, rid, with_for_update=True)
        if row is None:
            raise NotFoundError(f"object {rid!r} not found")
        row.deleted_at = None
        row.version = row.version + 1
        await self.session.flush()
        return _to_object(row)

    # -- helpers -----------------------------------------------------------
    async def _check_unique(
        self,
        obj_def: ObjectTypeDef,
        properties: dict[str, Any],
        *,
        exclude_rid: str | None,
    ) -> None:
        from ontology_runtime.errors import ValidationFailed

        violations: list[dict[str, Any]] = []
        for name, prop in obj_def.properties.items():
            if name != obj_def.primaryKey and not prop.unique:
                continue
            value = properties.get(name)
            if value is None:
                continue
            stmt = (
                select(literal(1))
                .select_from(ObjectRow)
                .where(ObjectRow.object_type == obj_def.apiName)
                .where(ObjectRow.deleted_at.is_(None))
                .where(ObjectRow.properties.op("->>")(name) == _as_text(value))
                .limit(1)
            )
            if exclude_rid:
                stmt = stmt.where(ObjectRow.rid != exclude_rid)
            if await self.session.scalar(stmt) is not None:
                violations.append(
                    {
                        "code": "duplicate_value",
                        "path": name,
                        "message": f"{obj_def.apiName}.{name} must be unique; {value!r} exists",
                    }
                )
        if violations:
            raise ValidationFailed(violations)


def _required(obj_def: ObjectTypeDef, name: str) -> bool:
    prop = obj_def.properties.get(name)
    return bool(prop and prop.required)


def _to_object(row: ObjectRow) -> OntologyObject:
    return OntologyObject(
        rid=row.rid,
        object_type=row.object_type,
        properties=dict(row.properties or {}),
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


def _as_text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


async def bulk_update_properties(session: AsyncSession, updates: dict[str, dict[str, Any]]) -> None:
    """Apply raw property dicts (used by functions after validation)."""
    for rid, properties in updates.items():
        await session.execute(
            update(ObjectRow)
            .where(ObjectRow.rid == rid)
            .values(properties=properties, updated_at=dt.datetime.now(dt.UTC))
        )
