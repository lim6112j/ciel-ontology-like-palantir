"""EditContext: a transactional read view with a read-your-writes overlay."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ontology_runtime.actions.edits import (
    EditBatch,
    LinkCreate,
    LinkDelete,
    ObjectCreate,
    ObjectDelete,
    ObjectModify,
)
from ontology_runtime.query.filter import compile_filter as _compile_filter  # noqa: F401
from ontology_runtime.query.object_set import ObjectSetService
from ontology_runtime.registry import SchemaRegistry
from ontology_runtime.store.object_store import OntologyObject


@dataclass
class EditContext:
    """Read view + pending edits for one action run.

    Reads consult already-appended edits first, so rule order never changes the
    outcome, and a dry run can be discarded by simply never applying the batch.
    """

    registry: SchemaRegistry
    session: AsyncSession
    actor: str = "unknown"
    params: dict[str, Any] = field(default_factory=dict)
    batch: EditBatch = field(default_factory=EditBatch)
    #: Per-invocation scratch space for functions (never persisted).
    scratch: dict[str, Any] = field(default_factory=dict)
    started_at: float = field(default_factory=time.monotonic)

    # -- overlay state -----------------------------------------------------
    @property
    def created(self) -> dict[str, ObjectCreate]:
        return {e.rid: e for e in self.batch.edits if isinstance(e, ObjectCreate)}

    @property
    def modified(self) -> dict[str, ObjectModify]:
        # Later edits win.
        return {e.rid: e for e in self.batch.edits if isinstance(e, ObjectModify)}

    @property
    def deleted(self) -> set[str]:
        return {e.rid for e in self.batch.edits if isinstance(e, ObjectDelete)}

    def pending_links(self) -> tuple[set[tuple[str, str, str]], set[tuple[str, str, str]]]:
        created = {
            (e.link_type, e.from_rid, e.to_rid)
            for e in self.batch.edits
            if isinstance(e, LinkCreate)
        }
        deleted = {
            (e.link_type, e.from_rid, e.to_rid)
            for e in self.batch.edits
            if isinstance(e, LinkDelete)
        }
        return created, deleted

    # -- reads -------------------------------------------------------------
    async def get(self, rid: str) -> OntologyObject | None:
        if rid in self.deleted:
            return None
        if rid in self.created:
            edit = self.created[rid]
            return OntologyObject(
                rid=edit.rid, object_type=edit.object_type, properties=dict(edit.properties)
            )
        if rid in self.modified:
            modify = self.modified[rid]
            merged = {**modify.before, **modify.properties}
            return OntologyObject(rid=modify.rid, object_type=modify.object_type, properties=merged)
        from ontology_runtime.store.object_store import ObjectStore

        return await ObjectStore(self.registry, self.session).maybe_get(rid)

    async def require(self, rid: str) -> OntologyObject:
        obj = await self.get(rid)
        if obj is None:
            from ontology_runtime.errors import NotFoundError

            raise NotFoundError(f"object {rid!r} not found")
        return obj

    async def search(self, object_type: str, filter: Any = None) -> list[OntologyObject]:
        """Search including pending creates/modifications and excluding pending deletes."""
        # A prior action in this session may have written rows the identity map
        # still caches; force the query to read current database state.
        await self.session.commit()
        service = ObjectSetService(self.registry, self.session)
        page = await service.search(object_type, filter=filter, page_size=500)
        by_rid: dict[str, OntologyObject] = {
            obj.rid: obj for obj in page.objects if obj.rid not in self.deleted
        }
        for rid, edit in self.created.items():
            if edit.object_type == object_type:
                by_rid[rid] = OntologyObject(
                    rid=rid, object_type=object_type, properties=dict(edit.properties)
                )
        for rid, modify in self.modified.items():
            if rid in by_rid:
                by_rid[rid] = OntologyObject(
                    rid=rid,
                    object_type=by_rid[rid].object_type,
                    properties={**by_rid[rid].properties, **modify.properties},
                )

        if filter is None:
            return list(by_rid.values())

        obj_def = self.registry.object_type(object_type)
        evaluate = _python_predicate(filter, obj_def.properties)
        return [obj for obj in by_rid.values() if evaluate(obj.properties)]

    # -- writes (append only) ---------------------------------------------
    def create(self, object_type: str, properties: dict[str, Any], rid: str | None = None) -> str:
        from ontology_runtime.store.object_store import ObjectStore, new_rid

        created_rid = rid or new_rid(object_type)
        if created_rid in self.created:
            raise ValueError(f"object {created_rid!r} already exists in this transaction")
        coerced, report = ObjectStore(self.registry, self.session).validate_properties(
            object_type, properties, partial=False
        )
        if not report.ok:
            from ontology_runtime.errors import ValidationFailed

            raise ValidationFailed(report.violations)
        self.batch.append(
            ObjectCreate(object_type=object_type, rid=created_rid, properties=coerced)
        )
        return created_rid

    async def modify(self, rid: str, properties: dict[str, Any]) -> None:
        current = await self.require(rid)
        from ontology_runtime.store.object_store import ObjectStore

        coerced, report = ObjectStore(self.registry, self.session).validate_properties(
            current.object_type, properties, partial=True
        )
        if not report.ok:
            from ontology_runtime.errors import ValidationFailed

            raise ValidationFailed(report.violations)
        if rid in self.created:
            self.created[rid].properties.update(coerced)
            return
        if rid in self.modified:
            self.modified[rid].properties.update(coerced)
            return
        self.batch.append(
            ObjectModify(
                object_type=current.object_type,
                rid=rid,
                properties=coerced,
                before=dict(current.properties),
            )
        )

    async def delete(self, rid: str) -> None:
        current = await self.require(rid)
        if rid in self.created:
            # Never persisted: drop the pending create instead.
            self.batch.edits = [
                e for e in self.batch.edits if not (isinstance(e, ObjectCreate) and e.rid == rid)
            ]
            return
        self.batch.append(
            ObjectDelete(object_type=current.object_type, rid=rid, before=dict(current.properties))
        )

    def link(self, link_type: str, from_rid: str, to_rid: str) -> None:
        self.batch.append(LinkCreate(link_type=link_type, from_rid=from_rid, to_rid=to_rid))

    def unlink(self, link_type: str, from_rid: str, to_rid: str) -> None:
        self.batch.append(LinkDelete(link_type=link_type, from_rid=from_rid, to_rid=to_rid))

    async def linked(self, rid: str, link_name: str) -> list[OntologyObject]:
        obj = await self.require(rid)
        view = self.registry.link_on(obj.object_type, link_name)
        created, deleted = self.pending_links()
        from ontology_runtime.store.link_store import LinkStore

        current = await LinkStore(self.registry, self.session).targets(view, rid)
        by_rid = {o.rid: o for o in current}
        for link_type, from_rid, to_rid in deleted:
            if link_type != view.link.apiName:
                continue
            if (view.is_forward and from_rid == rid) or (not view.is_forward and to_rid == rid):
                target = to_rid if view.is_forward else from_rid
                by_rid.pop(target, None)
        for link_type, from_rid, to_rid in created:
            if link_type != view.link.apiName:
                continue
            if (view.is_forward and from_rid == rid) or (not view.is_forward and to_rid == rid):
                target = to_rid if view.is_forward else from_rid
                pending = await self.get(target)
                if pending is not None:
                    by_rid[target] = pending
        return list(by_rid.values())


def _python_predicate(filter: Any, properties: dict[str, Any]) -> Callable[[dict[str, Any]], bool]:
    """Python-side filter for overlay rows. Mirrors the SQL semantics used in search."""

    def evaluate(values: dict[str, Any]) -> bool:
        return _matches(filter, values, properties)

    return evaluate


def _matches(spec: Any, values: dict[str, Any], properties: dict[str, Any]) -> bool:
    if not spec:
        return True
    if "and" in spec:
        return all(_matches(child, values, properties) for child in spec["and"])
    if "or" in spec:
        return any(_matches(child, values, properties) for child in spec["or"])
    if "not" in spec:
        return not _matches(spec["not"], values, properties)

    name = spec.get("field")
    if name not in properties:
        return False
    prop = properties[name]
    actual = values.get(name)
    op = spec.get("op", "eq")
    if op == "isNull":
        expected = spec.get("value", True)
        return (actual is None) == bool(expected)

    try:
        # Compare in the property's canonical storage form. The SQL binding path
        # (`filter._coerce`) converts dates/timestamps into Python objects, but
        # overlay rows still hold the JSON representation, so normalizing both
        # through `prop.coerce` keeps the two paths semantically identical.
        expected = prop.coerce(spec.get("value"))
        actual = prop.coerce(actual) if actual is not None else None
    except ValueError:
        return False
    try:
        if op == "eq":
            return bool(actual == expected)
        if op == "ne":
            return bool(actual != expected)
        if op == "gt":
            return actual is not None and actual > expected
        if op == "gte":
            return actual is not None and actual >= expected
        if op == "lt":
            return actual is not None and actual < expected
        if op == "lte":
            return actual is not None and actual <= expected
        if op == "in":
            return actual in spec.get("value", [])
        if op == "contains":
            return isinstance(actual, str) and str(expected) in actual
        if op == "startswith":
            return isinstance(actual, str) and actual.startswith(str(expected))
    except TypeError:
        return False
    return False
