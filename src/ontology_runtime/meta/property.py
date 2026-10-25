"""Property definitions and their mapping to Python / PostgreSQL types."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class PropertyType(StrEnum):
    STRING = "string"
    TEXT = "text"
    INTEGER = "integer"
    BIGINT = "bigint"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    TIMESTAMP = "timestamp"
    ENUM = "enum"
    OBJECT_REF = "objectRef"
    JSON = "json"


#: PostgreSQL cast applied when the property is indexed or filtered.
SQL_CAST: dict[PropertyType, str] = {
    PropertyType.STRING: "text",
    PropertyType.TEXT: "text",
    PropertyType.INTEGER: "integer",
    PropertyType.BIGINT: "bigint",
    PropertyType.DECIMAL: "numeric",
    PropertyType.BOOLEAN: "boolean",
    PropertyType.DATE: "date",
    PropertyType.TIMESTAMP: "timestamptz",
    PropertyType.ENUM: "text",
    PropertyType.OBJECT_REF: "text",
    PropertyType.JSON: "jsonb",
}

#: Python types accepted for each property type (None is always allowed unless required).
PYTHON_TYPE: dict[PropertyType, tuple[type, ...]] = {
    PropertyType.STRING: (str,),
    PropertyType.TEXT: (str,),
    PropertyType.INTEGER: (int,),
    PropertyType.BIGINT: (int,),
    PropertyType.DECIMAL: (int, float),
    PropertyType.BOOLEAN: (bool,),
    PropertyType.DATE: (dt.date, str),
    PropertyType.TIMESTAMP: (dt.datetime, str),
    PropertyType.ENUM: (str,),
    PropertyType.OBJECT_REF: (str, dict),
    PropertyType.JSON: (dict, list),
}


class PropertyDef(BaseModel):
    model_config = {"extra": "forbid"}

    apiName: str = Field(pattern=r"^[a-z][a-zA-Z0-9]*$")
    displayName: str | None = None
    type: PropertyType
    description: str | None = None
    required: bool = False
    indexed: bool = False
    unique: bool = False

    # enum
    values: list[str] | None = None
    # objectRef
    objectType: str | None = None
    # numeric / string bounds
    min: float | None = None
    max: float | None = None
    minLength: int | None = None
    maxLength: int | None = None
    defaultValue: Any = None

    @model_validator(mode="after")
    def _check_type_specific_fields(self) -> PropertyDef:
        if self.type is PropertyType.ENUM and not self.values:
            raise ValueError(f"property {self.apiName!r}: enum requires 'values'")
        if self.type is PropertyType.OBJECT_REF and not self.objectType:
            raise ValueError(f"property {self.apiName!r}: objectRef requires 'objectType'")
        if self.type is not PropertyType.ENUM and self.values:
            raise ValueError(f"property {self.apiName!r}: 'values' is only valid for enum")
        if self.type is not PropertyType.OBJECT_REF and self.objectType:
            raise ValueError(f"property {self.apiName!r}: 'objectType' is only valid for objectRef")
        return self

    def coerce(self, value: Any) -> Any:
        """Validate and normalize a raw property value.

        Raises ValueError with a human-readable message on failure.
        """
        if value is None:
            if self.required and self.defaultValue is None:
                raise ValueError(f"{self.apiName}: required property is missing")
            return None

        if self.type is PropertyType.INTEGER or self.type is PropertyType.BIGINT:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{self.apiName}: expected integer, got {type(value).__name__}")
        elif self.type is PropertyType.DECIMAL:
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise ValueError(f"{self.apiName}: expected number, got {type(value).__name__}")
        elif self.type is PropertyType.BOOLEAN:
            if not isinstance(value, bool):
                raise ValueError(f"{self.apiName}: expected boolean, got {type(value).__name__}")
        elif self.type is PropertyType.DATE:
            value = _coerce_date(self.apiName, value)
        elif self.type is PropertyType.TIMESTAMP:
            value = _coerce_timestamp(self.apiName, value)
        elif self.type is PropertyType.ENUM:
            if value not in (self.values or []):
                raise ValueError(f"{self.apiName}: {value!r} is not one of {self.values}")
        elif self.type is PropertyType.OBJECT_REF:
            if isinstance(value, dict):
                value = value.get("rid")
            if not isinstance(value, str) or not value.startswith("ri."):
                raise ValueError(f"{self.apiName}: expected an object rid, got {value!r}")
        elif self.type is PropertyType.STRING or self.type is PropertyType.TEXT:
            if not isinstance(value, str):
                raise ValueError(f"{self.apiName}: expected string, got {type(value).__name__}")
        elif self.type is PropertyType.JSON and not isinstance(value, dict | list):
            raise ValueError(f"{self.apiName}: expected JSON object or array")

        if self.min is not None and isinstance(value, int | float) and value < self.min:
            raise ValueError(f"{self.apiName}: {value} is below minimum {self.min}")
        if self.max is not None and isinstance(value, int | float) and value > self.max:
            raise ValueError(f"{self.apiName}: {value} is above maximum {self.max}")
        if self.minLength is not None and isinstance(value, str) and len(value) < self.minLength:
            raise ValueError(f"{self.apiName}: shorter than minimum length {self.minLength}")
        if self.maxLength is not None and isinstance(value, str) and len(value) > self.maxLength:
            raise ValueError(f"{self.apiName}: longer than maximum length {self.maxLength}")
        return value


def _coerce_date(api_name: str, value: Any) -> str:
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value).isoformat()
        except ValueError as exc:
            raise ValueError(f"{api_name}: invalid date {value!r}") from exc
    raise ValueError(f"{api_name}: expected date, got {type(value).__name__}")


def _coerce_timestamp(api_name: str, value: Any) -> str:
    if isinstance(value, dt.datetime):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
        except ValueError as exc:
            raise ValueError(f"{api_name}: invalid timestamp {value!r}") from exc
    raise ValueError(f"{api_name}: expected timestamp, got {type(value).__name__}")
