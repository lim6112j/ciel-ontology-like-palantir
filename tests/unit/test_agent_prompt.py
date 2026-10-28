"""The system prompt grounds agents in the served schema."""

from __future__ import annotations

import pytest

from ontology_runtime.agents.loop import _system_prompt
from ontology_runtime.registry import SchemaRegistry


@pytest.fixture(scope="module")
def bakery_registry() -> SchemaRegistry:
    return SchemaRegistry.from_domain("bakery")


@pytest.fixture(scope="module")
def liquor_registry() -> SchemaRegistry:
    return SchemaRegistry.from_domain("liquor")


def test_prompt_lists_every_object_type(bakery_registry: SchemaRegistry) -> None:
    agent = bakery_registry.agent("bakeryOpsAgent")
    prompt = _system_prompt(agent, bakery_registry)

    for name in bakery_registry.bundle.object_types:
        assert name in prompt, f"object type {name} missing from system prompt"


def test_prompt_includes_korean_display_names(bakery_registry: SchemaRegistry) -> None:
    agent = bakery_registry.agent("bakeryOpsAgent")
    prompt = _system_prompt(agent, bakery_registry)

    # 폐기기록: the exact alias confusion that once made an agent deny its existence.
    assert "WasteRecord" in prompt
    assert "폐기기록" in prompt


def test_prompt_lists_agent_allowed_actions_and_functions(
    bakery_registry: SchemaRegistry,
) -> None:
    agent = bakery_registry.agent("batchPlannerAgent")
    prompt = _system_prompt(agent, bakery_registry)

    for action in agent.allowedActionTypes:
        assert action in prompt
    for fn in agent.allowedFunctions:
        assert fn in prompt


def test_prompt_lists_links(bakery_registry: SchemaRegistry) -> None:
    agent = bakery_registry.agent("bakeryOpsAgent")
    prompt = _system_prompt(agent, bakery_registry)

    for name in bakery_registry.bundle.link_types:
        assert name in prompt


def test_prompt_never_asserts_absence_without_verification(
    bakery_registry: SchemaRegistry,
) -> None:
    agent = bakery_registry.agent("bakeryOpsAgent")
    prompt = _system_prompt(agent, bakery_registry)

    assert "단정하기 전" in prompt or "단정하지" in prompt


def test_injection_works_for_every_agent_of_every_domain() -> None:
    for domain in ("liquor", "bakery"):
        registry = SchemaRegistry.from_domain(domain)
        for agent in registry.bundle.agents.values():
            prompt = _system_prompt(agent, registry)
            assert agent.systemPrompt in prompt
            for name in registry.bundle.object_types:
                assert name in prompt, f"{domain}/{agent.apiName}: {name} missing"
