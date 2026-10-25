"""Meta-model unit tests: property/param validation and definition constraints."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from ontology_runtime.meta import (
    ActionTypeDef,
    LinkTypeDef,
    ObjectTypeDef,
    ParameterDef,
    ParameterType,
    PropertyDef,
    RunFunctionRule,
    StateMachineDef,
)


def _prop(**kw) -> dict:
    base = {"apiName": "name", "type": "string"}
    base.update(kw)
    return base


def _object(**kw) -> dict:
    base = {
        "apiName": "Outlet",
        "displayName": "거래처",
        "primaryKey": "outletNo",
        "properties": {
            "outletNo": _prop(apiName="outletNo"),
            "status": _prop(apiName="status", type="enum", values=["active", "closed"]),
        },
    }
    base.update(kw)
    return base


class TestPropertyDef:
    def test_string_accepts_str(self) -> None:
        prop = PropertyDef(**_prop())
        assert prop.coerce("hello") == "hello"

    def test_integer_rejects_bool(self) -> None:
        prop = PropertyDef(**_prop(apiName="qty", type="integer"))
        with pytest.raises(ValueError, match="expected integer"):
            prop.coerce(True)

    def test_enum_rejects_unknown_value(self) -> None:
        prop = PropertyDef(**_prop(apiName="status", type="enum", values=["a"]))
        with pytest.raises(ValueError, match="is not one of"):
            prop.coerce("b")

    def test_date_normalizes_to_iso_string(self) -> None:
        prop = PropertyDef(**_prop(apiName="due", type="date"))
        assert prop.coerce(dt.date(2026, 10, 25)) == "2026-10-25"

    def test_object_ref_accepts_dict_and_extracts_rid(self) -> None:
        prop = PropertyDef(**_prop(apiName="outlet", type="objectRef", objectType="Outlet"))
        assert prop.coerce({"objectType": "Outlet", "rid": "ri.x.object.1"}) == "ri.x.object.1"

    def test_object_ref_rejects_non_rid(self) -> None:
        prop = PropertyDef(**_prop(apiName="outlet", type="objectRef", objectType="Outlet"))
        with pytest.raises(ValueError, match="expected an object rid"):
            prop.coerce("Outlet")

    def test_required_missing_raises(self) -> None:
        prop = PropertyDef(**_prop(required=True))
        with pytest.raises(ValueError, match="required property is missing"):
            prop.coerce(None)

    def test_optional_missing_is_none(self) -> None:
        prop = PropertyDef(**_prop())
        assert prop.coerce(None) is None

    def test_bounds_enforced(self) -> None:
        prop = PropertyDef(**_prop(apiName="boxes", type="integer", min=1, max=100))
        with pytest.raises(ValueError, match="below minimum"):
            prop.coerce(0)
        with pytest.raises(ValueError, match="above maximum"):
            prop.coerce(101)

    def test_enum_requires_values(self) -> None:
        with pytest.raises(ValidationError, match="enum requires 'values'"):
            PropertyDef(**_prop(apiName="status", type="enum"))


class TestObjectTypeDef:
    def test_valid_object_type(self) -> None:
        obj = ObjectTypeDef(**_object())
        assert obj.primaryKey == "outletNo"

    def test_primary_key_must_exist(self) -> None:
        with pytest.raises(ValidationError, match="primaryKey 'missing' not declared"):
            ObjectTypeDef(**_object(primaryKey="missing"))

    def test_property_key_must_match_api_name(self) -> None:
        bad = _object()
        bad["properties"]["otherName"] = _prop(apiName="name")
        with pytest.raises(ValidationError, match="does not match apiName"):
            ObjectTypeDef(**bad)

    def test_state_machine_states_must_be_enum_values(self) -> None:
        machine = StateMachineDef(
            initial="active",
            transitions=[{"from": "active", "to": "nope"}],
        )
        with pytest.raises(ValidationError, match="unknown state"):
            ObjectTypeDef(**_object(stateMachine=machine))

    def test_state_machine_allows_wildcard_source(self) -> None:
        machine = StateMachineDef(initial="active", transitions=[{"from": "*", "to": "closed"}])
        assert machine.allows("active", "closed")
        assert machine.allows("closed", "closed")

    def test_index_must_reference_known_property(self) -> None:
        with pytest.raises(ValidationError, match="unknown properties"):
            ObjectTypeDef(**_object(indexes=[{"name": "ix", "properties": ["ghost"]}]))


class TestActionTypeDef:
    def _action(self, **kw) -> dict:
        base = {
            "apiName": "CreateSalesOrder",
            "displayName": "발주 생성",
            "parameters": {
                "outlet": {"apiName": "outlet", "type": "objectRef", "objectType": "Outlet"}
            },
            "rules": [{"type": "deleteObject", "target": {"param": "outlet"}}],
        }
        base.update(kw)
        return base

    def test_valid_action(self) -> None:
        action = ActionTypeDef(**self._action())
        assert action.is_function_backed() is False

    def test_run_function_cannot_combine_with_other_rules(self) -> None:
        with pytest.raises(ValidationError, match="cannot be combined"):
            ActionTypeDef(
                **self._action(
                    rules=[
                        {"type": "runFunction", "function": "doThing"},
                        {"type": "deleteObject", "target": {"param": "outlet"}},
                    ]
                )
            )

    def test_rule_must_reference_declared_parameter(self) -> None:
        with pytest.raises(ValidationError, match="unknown parameter 'ghost'"):
            ActionTypeDef(
                **self._action(rules=[{"type": "deleteObject", "target": {"param": "ghost"}}])
            )

    def test_validator_field_must_be_declared(self) -> None:
        with pytest.raises(ValidationError, match="validator references unknown parameter"):
            ActionTypeDef(**self._action(validators=[{"field": "ghost", "rule": "required"}]))

    def test_object_parameter_requires_object_type(self) -> None:
        with pytest.raises(ValidationError, match="requires 'objectType'"):
            ParameterDef(apiName="p", type=ParameterType.OBJECT_REF)

    def test_agent_parameters_excludes_hidden(self) -> None:
        action = ActionTypeDef(
            **self._action(
                parameters={
                    "outlet": {"apiName": "outlet", "type": "objectRef", "objectType": "Outlet"},
                    "secret": {"apiName": "secret", "type": "string", "agentVisible": False},
                },
                rules=[{"type": "deleteObject", "target": {"param": "outlet"}}],
            )
        )
        assert set(action.agent_parameters()) == {"outlet"}

    def test_function_backed_action_exposes_function_name(self) -> None:
        action = ActionTypeDef(**self._action(rules=[{"type": "runFunction", "function": "plan"}]))
        assert isinstance(action.rules[0], RunFunctionRule)
        assert action.function_name() == "plan"


class TestLinkTypeDef:
    def test_inverse_names_default(self) -> None:
        link = LinkTypeDef(
            apiName="orders",
            displayName="발주",
            fromObjectType="Outlet",
            toObjectType="SalesOrder",
        )
        assert link.source_link_name() == "orders"
        assert link.target_link_name() == "orders"

    def test_inverse_names_explicit(self) -> None:
        link = LinkTypeDef(
            apiName="orders",
            displayName="발주",
            fromObjectType="Outlet",
            fromApiName="orders",
            toObjectType="SalesOrder",
            toApiName="outlet",
        )
        assert link.target_link_name() == "outlet"
