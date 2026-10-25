"""Action type definitions: parameters, declarative rules, and validators."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ParameterType(StrEnum):
    STRING = "string"
    TEXT = "text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    TIMESTAMP = "timestamp"
    ENUM = "enum"
    OBJECT_REF = "objectRef"
    OBJECT_SET = "objectSet"
    JSON = "json"


class ParameterDef(BaseModel):
    model_config = {"extra": "forbid"}

    apiName: str = Field(pattern=r"^[a-z][a-zA-Z0-9]*$")
    displayName: str | None = None
    type: ParameterType
    description: str | None = None
    required: bool = True
    objectType: str | None = None
    values: list[str] | None = None
    defaultValue: Any = None
    #: Expose this parameter to agents proposing the action (default: true).
    agentVisible: bool = True

    @model_validator(mode="after")
    def _check_type_specific(self) -> ParameterDef:
        if self.type in (ParameterType.OBJECT_REF, ParameterType.OBJECT_SET):
            if not self.objectType:
                raise ValueError(f"parameter {self.apiName!r}: {self.type} requires 'objectType'")
        elif self.objectType:
            raise ValueError(
                f"parameter {self.apiName!r}: 'objectType' is only valid for objectRef/objectSet"
            )
        if self.type is ParameterType.ENUM and not self.values:
            raise ValueError(f"parameter {self.apiName!r}: enum requires 'values'")
        return self


class ValidatorDef(BaseModel):
    """Declarative parameter validator.

    Supported rules: required, range, regex, enum, compare, exists, unique.
    """

    model_config = {"extra": "forbid"}

    field: str
    rule: str
    value: Any = None
    other: str | None = None
    objectType: str | None = None
    property: str | None = None
    message: str | None = None


class ModifyPropertyDef(BaseModel):
    model_config = {"extra": "forbid"}

    property: str
    value: Any = None
    #: Copy the value of an action parameter.
    fromParam: str | None = None
    #: Increment the current value by a constant.
    incrementBy: int | None = None


class ObjectSelector(BaseModel):
    """How a rule identifies its target object."""

    model_config = {"extra": "forbid"}

    #: Name of an objectRef/objectSet parameter holding the target(s).
    param: str | None = None
    #: Fixed object type when the parameter does not pin it.
    objectType: str | None = None

    @model_validator(mode="after")
    def _at_least_one(self) -> ObjectSelector:
        if not self.param and not self.objectType:
            raise ValueError("object selector requires 'param' or 'objectType'")
        return self


class RuleBase(BaseModel):
    model_config = {"extra": "forbid", "populate_by_name": True}


class CreateObjectRule(RuleBase):
    type: str = "createObject"
    objectType: str
    #: Assign the new rid to an action parameter so later rules can reference it.
    assignRidTo: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class ModifyObjectRule(RuleBase):
    type: str = "modifyObject"
    target: ObjectSelector
    expectedStatus: list[str] | None = None
    properties: list[ModifyPropertyDef] = Field(default_factory=list)


class DeleteObjectRule(RuleBase):
    type: str = "deleteObject"
    target: ObjectSelector


class CreateLinkRule(RuleBase):
    type: str = "createLink"
    linkType: str
    fromParam: str
    toParam: str


class DeleteLinkRule(RuleBase):
    type: str = "deleteLink"
    linkType: str
    fromParam: str
    toParam: str


class RunFunctionRule(RuleBase):
    type: str = "runFunction"
    function: str


ActionRule = (
    CreateObjectRule
    | ModifyObjectRule
    | DeleteObjectRule
    | CreateLinkRule
    | DeleteLinkRule
    | RunFunctionRule
)

RULE_KINDS: dict[str, type[RuleBase]] = {
    "createObject": CreateObjectRule,
    "modifyObject": ModifyObjectRule,
    "deleteObject": DeleteObjectRule,
    "createLink": CreateLinkRule,
    "deleteLink": DeleteLinkRule,
    "runFunction": RunFunctionRule,
}


class ActionTypeDef(BaseModel):
    model_config = {"extra": "forbid"}

    apiName: str = Field(pattern=r"^[A-Za-z][a-zA-Z0-9]*$")
    displayName: str
    description: str | None = None
    parameters: dict[str, ParameterDef] = Field(default_factory=dict)
    rules: list[ActionRule] = Field(default_factory=list)
    validators: list[ValidatorDef] = Field(default_factory=list)
    allowedRoles: list[str] = Field(default_factory=list)
    #: Whether agents may propose this action at all.
    agentProposable: bool = True

    @model_validator(mode="after")
    def _check(self) -> ActionTypeDef:
        for name, param in self.parameters.items():
            if param.apiName != name:
                raise ValueError(
                    f"action {self.apiName!r}: parameter key {name!r} "
                    f"does not match apiName {param.apiName!r}"
                )
        if not self.rules:
            raise ValueError(f"action {self.apiName!r}: at least one rule is required")

        function_rules = [r for r in self.rules if isinstance(r, RunFunctionRule)]
        if function_rules and len(self.rules) > 1:
            raise ValueError(
                f"action {self.apiName!r}: a runFunction rule cannot be combined with other rules"
            )

        param_names = set(self.parameters)
        for validator in self.validators:
            if validator.field not in param_names:
                raise ValueError(
                    f"action {self.apiName!r}: validator references unknown "
                    f"parameter {validator.field!r}"
                )
            if validator.other and validator.other not in param_names:
                raise ValueError(
                    f"action {self.apiName!r}: validator compares against unknown "
                    f"parameter {validator.other!r}"
                )
            if validator.rule not in VALIDATOR_RULES:
                raise ValueError(
                    f"action {self.apiName!r}: unknown validator rule {validator.rule!r}; "
                    f"expected one of {sorted(VALIDATOR_RULES)}"
                )

        for rule in self.rules:
            for ref in _rule_param_refs(rule):
                if ref not in param_names:
                    raise ValueError(
                        f"action {self.apiName!r}: rule references unknown parameter {ref!r}"
                    )
        return self

    def is_function_backed(self) -> bool:
        return any(isinstance(r, RunFunctionRule) for r in self.rules)

    def function_name(self) -> str | None:
        for rule in self.rules:
            if isinstance(rule, RunFunctionRule):
                return rule.function
        return None

    def agent_parameters(self) -> dict[str, ParameterDef]:
        return {k: v for k, v in self.parameters.items() if v.agentVisible}


VALIDATOR_RULES = {"required", "range", "regex", "enum", "compare", "exists", "unique"}


def property_param_refs(properties: dict[str, Any]) -> set[str]:
    """Parameter references inside `{"param": "name"}` property values."""
    return {
        value["param"]
        for value in properties.values()
        if isinstance(value, dict) and isinstance(value.get("param"), str)
    }


def _rule_param_refs(rule: ActionRule) -> set[str]:
    refs: set[str] = set()
    if isinstance(rule, CreateObjectRule):
        refs |= property_param_refs(rule.properties)
    elif isinstance(rule, ModifyObjectRule):
        if rule.target.param:
            refs.add(rule.target.param)
        refs |= {p.fromParam for p in rule.properties if p.fromParam}
    elif isinstance(rule, DeleteObjectRule):
        if rule.target.param:
            refs.add(rule.target.param)
    elif isinstance(rule, CreateLinkRule | DeleteLinkRule):
        refs |= {rule.fromParam, rule.toParam}
    return refs
