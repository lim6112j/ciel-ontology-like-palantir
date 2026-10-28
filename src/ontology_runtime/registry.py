"""Runtime registry over a loaded SchemaBundle.

Derives inverse links and PostgreSQL index DDL, and provides the lookup
surface used by stores, actions, functions, agents, and the API.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ontology_runtime.errors import (
    ActionNotFound,
    LinkTypeNotFound,
    ObjectTypeNotFound,
    SchemaError,
)
from ontology_runtime.loader import SchemaBundle, load_schema
from ontology_runtime.meta import (
    ActionTypeDef,
    AgentDef,
    Cardinality,
    DomainManifest,
    FunctionDef,
    LinkTypeDef,
    ObjectTypeDef,
    PropertyType,
)
from ontology_runtime.meta.property import SQL_CAST

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class ResolvedIndex:
    """An index ready to be rendered as DDL."""

    name: str
    object_type: str
    expressions: tuple[str, ...]
    unique: bool
    where: str | None
    #: Domain RID namespace; index names are prefixed with it so two domains
    #: with a same-named type never collide on the global `ontology_indexes` PK.
    namespace: str = "ont"

    def ddl(self) -> str:
        unique = "UNIQUE " if self.unique else ""
        columns = ", ".join(self.expressions)
        clauses = [f"object_type = '{self.object_type}'"]
        if self.where:
            clauses.append(f"({self.where})")
        clauses.append("deleted_at IS NULL")
        where = " AND ".join(clauses)
        return f"CREATE {unique}INDEX {self.name} ON objects ({columns}) WHERE {where}"


@dataclass(frozen=True)
class LinkView:
    """One direction of a link type, as seen from a particular object type."""

    link: LinkTypeDef
    object_type: str
    link_name: str
    target_type: str
    is_forward: bool
    cardinality: Cardinality

    @property
    def inverse_cardinality(self) -> Cardinality:
        return self.link.fromCardinality if self.is_forward else self.link.toCardinality


class SchemaRegistry:
    def __init__(self, bundle: SchemaBundle) -> None:
        self.bundle = bundle
        self._links_by_type: dict[str, list[LinkView]] = {}
        self._link_lookup: dict[tuple[str, str], LinkView] = {}
        self._build_link_views()

    @classmethod
    def from_directory(
        cls, schema_dir: Path, *, platform_dir: Path | None = None
    ) -> SchemaRegistry:
        return cls(load_schema(schema_dir, platform_dir=platform_dir))

    @classmethod
    def from_domain(
        cls,
        name: str,
        *,
        domains_dir: Path | None = None,
        platform_dir: Path | None = None,
    ) -> SchemaRegistry:
        """Load one domain with the shared platform definitions merged in."""
        from ontology_runtime.config import DOMAINS_DIR, PLATFORM_DIR

        base = domains_dir or DOMAINS_DIR
        directory = base / name
        if not (directory / "domain.yaml").exists():
            available = sorted(p.name for p in base.iterdir() if (p / "domain.yaml").exists())
            raise SchemaError(
                f"unknown domain {name!r}; available: {', '.join(available) or '(none)'}"
            )
        return cls.from_directory(directory, platform_dir=platform_dir or PLATFORM_DIR)

    @property
    def domain(self) -> DomainManifest | None:
        return self.bundle.domain

    @property
    def domain_name(self) -> str:
        return self.bundle.domain_name

    @property
    def namespace(self) -> str:
        """RID namespace and index prefix. Bare schemas keep the original `ont`."""
        domain = self.bundle.domain
        return domain.namespace if domain else "ont"

    # -- lookups -----------------------------------------------------------
    def object_type(self, api_name: str) -> ObjectTypeDef:
        try:
            return self.bundle.object_types[api_name]
        except KeyError as exc:
            raise ObjectTypeNotFound(f"unknown object type {api_name!r}") from exc

    def maybe_object_type(self, api_name: str) -> ObjectTypeDef | None:
        return self.bundle.object_types.get(api_name)

    def link_type(self, api_name: str) -> LinkTypeDef:
        try:
            return self.bundle.link_types[api_name]
        except KeyError as exc:
            raise LinkTypeNotFound(f"unknown link type {api_name!r}") from exc

    def action_type(self, api_name: str) -> ActionTypeDef:

        action: ActionTypeDef | None = self.bundle.action_types.get(api_name)
        if action is None:
            raise ActionNotFound(f"unknown action type {api_name!r}")
        return action

    def function(self, api_name: str) -> FunctionDef:
        from ontology_runtime.errors import FunctionNotFound

        fn = self.bundle.functions.get(api_name)
        if fn is None:
            raise FunctionNotFound(f"unknown function {api_name!r}")
        return fn

    def agent(self, api_name: str) -> AgentDef:
        from ontology_runtime.errors import NotFoundError

        agent = self.bundle.agents.get(api_name)
        if agent is None:
            raise NotFoundError(f"unknown agent {api_name!r}")
        return agent

    # -- links -------------------------------------------------------------
    def links_of(self, object_type: str) -> list[LinkView]:
        """All links available on an object type, in both directions."""
        return self._links_by_type.get(object_type, [])

    def link_on(self, object_type: str, link_name: str) -> LinkView:
        view = self._link_lookup.get((object_type, link_name))
        if view is None:
            raise LinkTypeNotFound(f"object type {object_type!r} has no link named {link_name!r}")
        return view

    def _build_link_views(self) -> None:
        for link in self.bundle.link_types.values():
            # `cardinality` is targets-per-source from this side's perspective:
            # the from side holds `fromCardinality`, the to side holds `toCardinality`.
            forward = LinkView(
                link=link,
                object_type=link.fromObjectType,
                link_name=link.source_link_name(),
                target_type=link.toObjectType,
                is_forward=True,
                cardinality=link.fromCardinality,
            )
            inverse = LinkView(
                link=link,
                object_type=link.toObjectType,
                link_name=link.target_link_name(),
                target_type=link.fromObjectType,
                is_forward=False,
                cardinality=link.toCardinality,
            )
            for view in (forward, inverse):
                self._links_by_type.setdefault(view.object_type, []).append(view)
                key = (view.object_type, view.link_name)
                if key in self._link_lookup:
                    raise SchemaError(
                        f"duplicate link name {view.link_name!r} on {view.object_type!r}"
                    )
                self._link_lookup[key] = view

    # -- indexes -----------------------------------------------------------
    def indexes(self) -> list[ResolvedIndex]:
        specs: list[ResolvedIndex] = []
        namespace = self.namespace
        for obj in self.bundle.object_types.values():
            declared: set[tuple[str, ...]] = set()
            for name in obj.indexed_properties():
                declared.add((name,))
                specs.append(
                    ResolvedIndex(
                        name=_index_name(namespace, obj.apiName, (name,)),
                        object_type=obj.apiName,
                        namespace=namespace,
                        expressions=(_expression(obj, name),),
                        unique=obj.properties[name].unique,
                        where=None,
                    )
                )
            for index in obj.indexes:
                key = tuple(index.properties)
                if key in declared:
                    continue
                declared.add(key)
                if not _IDENT.match(index.name):
                    raise SchemaError(
                        f"object type {obj.apiName!r}: invalid index name {index.name!r}"
                    )
                specs.append(
                    ResolvedIndex(
                        name=index.name,
                        object_type=obj.apiName,
                        namespace=namespace,
                        expressions=tuple(_expression(obj, p) for p in index.properties),
                        unique=index.unique,
                        where=index.where,
                    )
                )
        return specs


def _expression(obj: ObjectTypeDef, property_name: str) -> str:
    prop = obj.properties[property_name]
    cast = SQL_CAST[prop.type]
    if prop.type is PropertyType.JSON:
        return f"(properties->'{property_name}')"
    if prop.type in (PropertyType.DATE, PropertyType.TIMESTAMP):
        # Casts to date/timestamptz are not IMMUTABLE and cannot be indexed.
        # ISO text keeps date ordering, so the text expression is sufficient.
        return f"(properties->>'{property_name}')"
    return f"((properties->>'{property_name}')::{cast})"


def _index_name(namespace: str, object_type: str, properties: tuple[str, ...]) -> str:
    joined = "_".join(properties)
    return f"ix_{namespace.lower()}_{object_type.lower()}_{joined.lower()}"
