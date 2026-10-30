"""Two domains coexist: same names, disjoint definitions, separate namespaces.

These tests need no database — the loader and registry are the whole surface.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ontology_runtime.errors import ObjectTypeNotFound, SchemaError
from ontology_runtime.loader import load_schema
from ontology_runtime.registry import SchemaRegistry


@pytest.fixture(scope="module")
def liquor() -> SchemaRegistry:
    return SchemaRegistry.from_domain("liquor")


@pytest.fixture(scope="module")
def bakery() -> SchemaRegistry:
    return SchemaRegistry.from_domain("bakery")


@pytest.fixture(scope="module")
def makgeolli() -> SchemaRegistry:
    return SchemaRegistry.from_domain("makgeolli")


def test_same_named_type_has_different_definitions(
    liquor: SchemaRegistry, bakery: SchemaRegistry
) -> None:
    # `Product` exists in both domains with deliberately different properties.
    liquor_product = liquor.object_type("Product")
    bakery_product = bakery.object_type("Product")

    assert "unitsPerCase" in liquor_product.properties
    assert "unitsPerCase" not in bakery_product.properties
    assert "shelfLifeDays" in bakery_product.properties
    assert "shelfLifeDays" not in liquor_product.properties
    assert liquor_product.primaryKey == "sku" == bakery_product.primaryKey


def test_makgeolli_product_brewing_properties_are_its_own(
    liquor: SchemaRegistry, makgeolli: SchemaRegistry
) -> None:
    # makgeolli reuses the Product name but carries brewing-specific properties.
    liquor_product = liquor.object_type("Product")
    makgeolli_product = makgeolli.object_type("Product")

    assert "fermentationDays" in makgeolli_product.properties
    assert "fermentationDays" not in liquor_product.properties
    assert "agingTempMinC" in makgeolli_product.properties
    assert "agingTempMinC" not in liquor_product.properties
    assert "unitsPerCase" not in makgeolli_product.properties


def test_object_types_do_not_leak_between_domains(
    liquor: SchemaRegistry, bakery: SchemaRegistry
) -> None:
    assert bakery.maybe_object_type("Store") is not None
    assert liquor.maybe_object_type("Store") is None
    with pytest.raises(ObjectTypeNotFound):
        liquor.object_type("Store")

    assert bakery.maybe_object_type("SalesOrder") is None
    with pytest.raises(ObjectTypeNotFound):
        bakery.object_type("SalesOrder")


def test_both_domains_load_platform_bookkeeping(
    liquor: SchemaRegistry, bakery: SchemaRegistry
) -> None:
    for registry in (liquor, bakery):
        assert "ActionProposal" in registry.bundle.object_types
        assert "AgentRun" in registry.bundle.object_types
        assert "ApproveActionProposal" in registry.bundle.action_types
        assert "proposalAgentRun" in registry.bundle.link_types
        assert "applyApprovedProposal" in registry.bundle.functions


def test_index_names_are_namespaced(liquor: SchemaRegistry, bakery: SchemaRegistry) -> None:
    liquor_names = {spec.name for spec in liquor.indexes()}
    bakery_names = {spec.name for spec in bakery.indexes()}

    assert all(name.startswith("ix_liquor_") for name in liquor_names)
    assert all(name.startswith("ix_bakery_") for name in bakery_names)
    assert not liquor_names & bakery_names


def test_domain_cannot_shadow_a_platform_type(tmp_path: Path) -> None:
    platform = tmp_path / "platform"
    (platform / "object_types").mkdir(parents=True)
    (platform / "object_types" / "ActionProposal.yaml").write_text(
        yaml.safe_dump(
            {
                "apiName": "ActionProposal",
                "displayName": "제안",
                "primaryKey": "proposalNo",
                "properties": {
                    "proposalNo": {"apiName": "proposalNo", "type": "string", "required": True}
                },
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    domain = tmp_path / "domains" / "rogue"
    (domain / "object_types").mkdir(parents=True)
    (domain / "domain.yaml").write_text("apiName: rogue\ndisplayName: Rogue\n", encoding="utf-8")
    (domain / "object_types" / "ActionProposal.yaml").write_text(
        (platform / "object_types" / "ActionProposal.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    with pytest.raises(SchemaError, match="redefines platform object type 'ActionProposal'"):
        load_schema(domain, platform_dir=platform)


def test_domain_manifest_name_must_match_directory(tmp_path: Path) -> None:
    domain = tmp_path / "wrong-dir"
    domain.mkdir()
    (domain / "domain.yaml").write_text("apiName: other\ndisplayName: Other\n", encoding="utf-8")
    with pytest.raises(SchemaError, match="does not match directory"):
        load_schema(domain)


def test_unknown_domain_lists_available(tmp_path: Path) -> None:
    (tmp_path / "known").mkdir()
    (tmp_path / "known" / "domain.yaml").write_text("apiName: known\ndisplayName: Known\n")
    with pytest.raises(SchemaError, match="available: known"):
        SchemaRegistry.from_domain("missing", domains_dir=tmp_path)
