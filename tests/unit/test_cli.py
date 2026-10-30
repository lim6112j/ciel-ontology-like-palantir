"""CLI commands that do not require a database."""

from __future__ import annotations

from pathlib import Path

from ontology_runtime.cli import main


def test_schema_validate_succeeds(capsys) -> None:
    from ontology_runtime.registry import SchemaRegistry

    assert main(["schema", "validate", "--domain", "liquor"]) == 0
    output = capsys.readouterr().out
    bundle = SchemaRegistry.from_domain("liquor").bundle
    assert "스키마 검증 통과" in output
    assert f"오브젝트 타입 {len(bundle.object_types)}" in output
    assert f"에이전트      {len(bundle.agents)}" in output


def test_domains_lists_all_domains(capsys) -> None:
    assert main(["domains"]) == 0
    output = capsys.readouterr().out
    assert "liquor" in output
    assert "bakery" in output
    assert "makgeolli" in output


def test_schema_validate_reports_errors(monkeypatch, capsys) -> None:
    from ontology_runtime import cli

    def boom():
        raise RuntimeError("broken schema")

    monkeypatch.setattr(cli, "_registry", boom)
    assert cli.main(["schema", "validate"]) == 1
    assert "스키마 오류" in capsys.readouterr().err


def test_export_client_writes_files(tmp_path: Path, capsys) -> None:
    target = tmp_path / "generated"
    assert main(["export-client", "--out", str(target)]) == 0
    assert (target / "objects.ts").exists()
    assert (target / "client.ts").exists()
    assert "TypeScript 클라이언트 생성" in capsys.readouterr().out


def test_export_web_writes_per_domain_clients_and_manifest(tmp_path: Path, capsys) -> None:
    import json

    target = tmp_path / "generated"
    assert main(["export-web", "--out", str(target)]) == 0

    assert (target / "liquor" / "client.ts").exists()
    assert (target / "bakery" / "client.ts").exists()
    assert (target / "makgeolli" / "client.ts").exists()

    manifest = json.loads((target / "domains.json").read_text(encoding="utf-8"))
    assert [entry["apiName"] for entry in manifest] == ["liquor", "bakery", "makgeolli"]
    assert manifest[0]["apiBase"] == "/api/liquor"

    ts = (target / "domains.ts").read_text(encoding="utf-8")
    assert "liquor: liquorApi," in ts
    assert "bakery: bakeryApi," in ts
    assert "웹 번들 생성" in capsys.readouterr().out


def test_docs_writes_markdown(tmp_path: Path, monkeypatch, capsys) -> None:
    from ontology_runtime import cli

    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    assert cli.main(["docs", "--domain", "liquor"]) == 0
    doc = tmp_path / "docs" / "domains" / "liquor" / "ontology.md"
    assert doc.exists()
    assert "오브젝트 타입" in doc.read_text(encoding="utf-8")
    assert str(doc) in capsys.readouterr().out
