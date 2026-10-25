"""Object type definitions: properties, state machines, and invariants."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from ontology_runtime.meta.property import PropertyDef, PropertyType

#: Type api names are PascalCase (OSDK convention); property/parameter names are camelCase.
API_NAME_PATTERN = r"^[A-Za-z][a-zA-Z0-9]*$"


class TransitionDef(BaseModel):
    """A status transition. `from` may be `*` to allow any state."""

    model_config = {"extra": "forbid"}

    from_: str = Field(alias="from")
    to: str


class StateMachineDef(BaseModel):
    model_config = {"extra": "forbid", "populate_by_name": True}

    property: str = "status"
    initial: str
    transitions: list[TransitionDef]

    def allows(self, from_state: str, to_state: str) -> bool:
        return any(t.to == to_state and (t.from_ in ("*", from_state)) for t in self.transitions)

    def targets(self) -> set[str]:
        return {t.to for t in self.transitions}


class InvariantDef(BaseModel):
    """A named, executable invariant implemented in Python.

    `params` are passed through to the registered invariant implementation.
    """

    model_config = {"extra": "forbid"}

    apiName: str
    description: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class IndexRef(BaseModel):
    """Explicit index declaration beyond simple `indexed: true`."""

    model_config = {"extra": "forbid"}

    name: str
    properties: list[str]
    unique: bool = False
    where: str | None = None


class ObjectTypeDef(BaseModel):
    model_config = {"extra": "forbid"}

    apiName: str = Field(pattern=API_NAME_PATTERN)
    displayName: str
    description: str | None = None
    pluralDisplayName: str | None = None
    primaryKey: str
    properties: dict[str, PropertyDef]
    stateMachine: StateMachineDef | None = None
    invariants: list[InvariantDef] = Field(default_factory=list)
    indexes: list[IndexRef] = Field(default_factory=list)
    interfaceRefs: list[str] = Field(default_factory=list)
    #: True for ontology-managed bookkeeping types an agent may not propose against.
    internal: bool = False

    @model_validator(mode="after")
    def _check_consistency(self) -> ObjectTypeDef:
        for name, prop in self.properties.items():
            if prop.apiName != name:
                raise ValueError(
                    f"object type {self.apiName!r}: property key {name!r} "
                    f"does not match apiName {prop.apiName!r}"
                )
        if self.primaryKey not in self.properties:
            raise ValueError(
                f"object type {self.apiName!r}: primaryKey {self.primaryKey!r} not declared"
            )
        if self.stateMachine:
            state_prop = self.properties.get(self.stateMachine.property)
            if state_prop is None:
                raise ValueError(
                    f"object type {self.apiName!r}: state machine property "
                    f"{self.stateMachine.property!r} not declared"
                )
            if state_prop.type is not PropertyType.ENUM:
                raise ValueError(
                    f"object type {self.apiName!r}: state machine property must be an enum"
                )
            states = set(state_prop.values or [])
            if self.stateMachine.initial not in states:
                raise ValueError(
                    f"object type {self.apiName!r}: initial state "
                    f"{self.stateMachine.initial!r} not in enum values"
                )
            for transition in self.stateMachine.transitions:
                unknown = {transition.to} - states
                if transition.from_ != "*":
                    unknown |= {transition.from_} - states
                if unknown:
                    raise ValueError(
                        f"object type {self.apiName!r}: transition references unknown "
                        f"state(s) {sorted(unknown)}"
                    )
        for index in self.indexes:
            unknown = set(index.properties) - set(self.properties)
            if unknown:
                raise ValueError(
                    f"object type {self.apiName!r}: index {index.name!r} references "
                    f"unknown properties {sorted(unknown)}"
                )
        return self

    def property(self, api_name: str) -> PropertyDef:
        try:
            return self.properties[api_name]
        except KeyError as exc:
            from ontology_runtime.errors import SchemaError

            raise SchemaError(f"{self.apiName} has no property {api_name!r}") from exc

    def indexed_properties(self) -> list[str]:
        return [name for name, prop in self.properties.items() if prop.indexed]
