"""Domain manifest validation and the generated landing-page manifest."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ontology_runtime.clientgen.web import render_domains_json, render_domains_ts
from ontology_runtime.meta import DomainManifest, WebConfig


def test_defaults_fill_in_a_usable_manifest() -> None:
    manifest = DomainManifest(apiName="acme", displayName="Acme")
    assert manifest.namespace == "acme"
    assert manifest.web_api_base == "/api/acme"
    assert manifest.web.enabled is True


def test_api_base_must_start_with_api_prefix() -> None:
    with pytest.raises(ValidationError, match="/api/<domain>"):
        WebConfig(apiBase="/wrong/acme")


def test_api_base_must_be_a_single_lowercase_segment() -> None:
    with pytest.raises(ValidationError):
        WebConfig(apiBase="/api/Acme")


def test_domain_name_must_be_lowercase_slug() -> None:
    with pytest.raises(ValidationError):
        DomainManifest(apiName="Bakery", displayName="Bakery")


def test_disabled_domains_are_excluded_and_entries_sorted() -> None:
    manifest_a = DomainManifest(
        apiName="aaa", displayName="A", web=WebConfig(order=20, tagline="a")
    )
    manifest_b = DomainManifest(
        apiName="bbb", displayName="B", web=WebConfig(order=10, tagline="b")
    )
    manifest_hidden = DomainManifest(
        apiName="ccc", displayName="C", web=WebConfig(enabled=False, order=1)
    )

    from ontology_runtime.clientgen.web import _domain_entries

    entries = _domain_entries([manifest_a, manifest_b, manifest_hidden])
    assert [entry["apiName"] for entry in entries] == ["bbb", "aaa"]


def test_rendered_manifest_is_valid_json_and_typescript() -> None:
    entries = [
        {
            "apiName": "liquor",
            "displayName": "주류",
            "description": None,
            "tagline": "t",
            "order": 10,
            "apiBase": "/api/liquor",
            "backendUrl": "http://localhost:8000",
        }
    ]
    parsed = json.loads(render_domains_json(entries))
    assert parsed[0]["apiName"] == "liquor"

    ts = render_domains_ts(entries)
    assert 'import { api as liquorApi } from "./liquor/client";' in ts
    assert "export const DOMAIN_APIS = {" in ts
    assert "liquor: liquorApi," in ts
