"""Allowlisted filter DSL compiled to SQLAlchemy expressions.

Two accepted shapes (mixing them in one node is rejected):

    {"field": "status", "op": "eq", "value": "active"}
    {"and": [ {...}, {...} ]}   {"or": [...]}   {"not": {...}}

Field names, operators, and comparison values are validated against the
object type's declared properties, so nothing user-supplied reaches SQL
as an identifier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import ColumnElement, and_, not_, or_
from sqlalchemy import cast as sa_cast
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import Boolean, Integer, Numeric, Text

from ontology_runtime.db.models import ObjectRow
from ontology_runtime.errors import ValidationFailed
from ontology_runtime.meta import PropertyDef, PropertyType

COMPARISON_OPS = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "contains", "startswith", "isNull"}
LOGICAL_OPS = {"and", "or", "not"}

_SQL_TYPE: dict[PropertyType, Any] = {
    PropertyType.STRING: Text,
    PropertyType.TEXT: Text,
    PropertyType.INTEGER: Integer,
    PropertyType.BIGINT: Integer,
    PropertyType.DECIMAL: Numeric,
    PropertyType.BOOLEAN: Boolean,
    # ISO-8601 date/timestamp strings sort identically to their temporal values,
    # so we compare them as text. This also keeps expression indexes creatable:
    # `(x)::date` is not IMMUTABLE, but `x` is.
    PropertyType.DATE: Text,
    PropertyType.TIMESTAMP: Text,
    PropertyType.ENUM: Text,
    PropertyType.OBJECT_REF: Text,
}
_JSON_TYPES = {PropertyType.JSON}


@dataclass
class FilterContext:
    object_type: str
    properties: dict[str, PropertyDef]
    violations: list[dict[str, Any]] = field(default_factory=list)

    def fail(self, path: str, message: str) -> None:
        self.violations.append({"code": "invalid_filter", "path": path, "message": message})


def compile_filter(
    object_type: str, properties: dict[str, PropertyDef], spec: Any
) -> ColumnElement[bool] | None:
    """Compile a filter specification; raises ValidationFailed on bad input."""
    context = FilterContext(object_type, properties)
    expression = _compile(context, spec, path="filter")
    if context.violations:
        raise ValidationFailed(context.violations)
    return expression


def _compile(context: FilterContext, spec: Any, *, path: str) -> ColumnElement[bool] | None:
    if spec is None:
        return None
    if not isinstance(spec, dict):
        context.fail(path, "filter node must be an object")
        return None

    logical = LOGICAL_OPS & set(spec)
    if logical:
        if len(logical) > 1 or set(spec) != logical:
            context.fail(path, f"logical node must contain exactly one of {sorted(LOGICAL_OPS)}")
            return None
        op = next(iter(logical))
        if op == "not":
            inner = _compile(context, spec[op], path=f"{path}.not")
            return not_(inner) if inner is not None else None
        children = spec[op]
        if not isinstance(children, list) or not children:
            context.fail(f"{path}.{op}", "expected a non-empty array")
            return None
        compiled = [
            _compile(context, child, path=f"{path}.{op}[{index}]")
            for index, child in enumerate(children)
        ]
        present = [c for c in compiled if c is not None]
        if not present:
            return None
        return and_(*present) if op == "and" else or_(*present)

    if "field" not in spec:
        context.fail(path, "filter node requires 'field' or a logical operator")
        return None
    return _compile_comparison(context, spec, path=path)


def _compile_comparison(
    context: FilterContext, spec: dict[str, Any], *, path: str
) -> ColumnElement[bool] | None:
    name = spec.get("field")
    op = spec.get("op", "eq")
    if not isinstance(name, str) or name not in context.properties:
        context.fail(f"{path}.field", f"{context.object_type} has no filterable property {name!r}")
        return None
    if op not in COMPARISON_OPS:
        context.fail(
            f"{path}.op", f"unknown operator {op!r}; expected one of {sorted(COMPARISON_OPS)}"
        )
        return None

    prop = context.properties[name]
    if prop.type is PropertyType.JSON:
        context.fail(f"{path}.field", f"{name!r} is a JSON property and cannot be filtered")
        return None

    path_name = f"{path}.value"
    if op == "isNull":
        expected = spec.get("value", True)
        is_null = _json_is_null(name)
        return is_null if expected else not_(is_null)

    if "value" not in spec:
        context.fail(path_name, "comparison requires 'value'")
        return None

    if op == "in":
        values = spec["value"]
        if not isinstance(values, list):
            context.fail(path_name, "'in' requires an array value")
            return None
        coerced = [_coerce(context, prop, value, path_name) for value in values]
        if any(v is _INVALID for v in coerced):
            return None
        return _column(prop, name).in_(coerced)

    if op in {"contains", "startswith"}:
        if prop.type not in (PropertyType.STRING, PropertyType.TEXT):
            context.fail(path_name, f"{op!r} is only valid for string properties")
            return None
        value = spec["value"]
        if not isinstance(value, str):
            context.fail(path_name, f"{op!r} requires a string value")
            return None
        text_column = _column(prop, name)
        if op == "contains":
            return text_column.contains(value)
        return text_column.startswith(value)

    value = _coerce(context, prop, spec["value"], path_name)
    if value is _INVALID:
        return None
    column: ColumnElement[Any] = _column(prop, name)
    if isinstance(value, bool):
        # SQLAlchemy maps `expr == True` to `expr IS true`, which PostgreSQL rejects
        # for a cast expression; compare explicitly instead.
        if op == "eq":
            return column.is_(value)
        if op == "ne":
            return column.is_not(value)
        return boolean_false()
    comparison: ColumnElement[bool] = {
        "eq": column == value,
        "ne": column != value,
        "gt": column > value,
        "gte": column >= value,
        "lt": column < value,
        "lte": column <= value,
    }[op]
    return comparison


def boolean_false() -> ColumnElement[bool]:
    """A non-null false predicate for meaningless ordering comparisons on booleans."""
    return ObjectRow.rid.is_(None)


_INVALID = object()


def _coerce(context: FilterContext, prop: PropertyDef, value: Any, path: str) -> Any:
    """Coerce to the Python type matching the SQL cast, so comparisons bind correctly."""
    try:
        coerced = prop.coerce(value)
    except ValueError as exc:
        context.fail(path, str(exc))
        return _INVALID
    if coerced is None:
        return None
    if prop.type is PropertyType.DATE or prop.type is PropertyType.TIMESTAMP:
        return str(coerced)
    if prop.type in (PropertyType.INTEGER, PropertyType.BIGINT):
        return int(coerced)
    if prop.type is PropertyType.DECIMAL:
        return float(coerced)
    if prop.type is PropertyType.BOOLEAN:
        return bool(coerced)
    return coerced


def _column(prop: PropertyDef, name: str) -> ColumnElement[Any]:
    """Typed SQL expression for one JSONB property."""
    raw = ObjectRow.properties.op("->>")(name)
    sql_type = _SQL_TYPE.get(prop.type, Text)
    return sa_cast(raw, sql_type)


def _json_is_null(name: str) -> ColumnElement[bool]:
    return ObjectRow.properties.op("->>")(name).is_(None)


def describe_filter(spec: Any) -> str:
    """Human-readable filter summary used in audit records and agent traces."""
    if not isinstance(spec, dict):
        return str(spec)
    if "field" in spec:
        return f"{spec.get('field')} {spec.get('op', 'eq')} {spec.get('value')!r}"
    for op in LOGICAL_OPS & set(spec):
        children = spec[op]
        if isinstance(children, list):
            return f"{op}({', '.join(describe_filter(c) for c in children)})"
        return f"not({describe_filter(children)})"
    return str(spec)


__all__ = [
    "COMPARISON_OPS",
    "FilterContext",
    "compile_filter",
    "describe_filter",
    "JSONB",
]
