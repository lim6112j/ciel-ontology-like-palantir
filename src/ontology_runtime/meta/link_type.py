"""Link type definitions."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Cardinality(StrEnum):
    ONE = "one"
    MANY = "many"


class LinkTypeDef(BaseModel):
    model_config = {"extra": "forbid"}

    apiName: str = Field(pattern=r"^[A-Za-z][a-zA-Z0-9]*$")
    displayName: str
    description: str | None = None
    fromObjectType: str
    #: Name of the link as seen from the source side (e.g. "stops" on Delivery).
    fromApiName: str | None = None
    fromCardinality: Cardinality = Cardinality.MANY
    toObjectType: str
    #: Name of the inverse link as seen from the target side (e.g. "delivery" on Stop).
    toApiName: str | None = None
    toCardinality: Cardinality = Cardinality.ONE

    def source_link_name(self) -> str:
        return self.fromApiName or self.apiName

    def target_link_name(self) -> str:
        return self.toApiName or self.apiName
