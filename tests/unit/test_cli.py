"""CLI commands that do not require a database."""

from __future__ import annotations

from pathlib import Path

from ontology_runtime.cli import main


def test_schema_validate_succeeds(capsys) -> None:
    assert main(["schema", "validate"]) == 0
    output = capsys.readouterr().out
    assert "스키마 검증 통과" in output
    assert "오브젝트 타입 16" in output
    assert "에이전트      4" in output


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


def test_docs_writes_markdown(tmp_path: Path, monkeypatch, capsys) -> None:
    from ontology_runtime import cli

    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    assert cli.main(["docs"]) == 0
    doc = tmp_path / "docs" / "ontology.md"
    assert doc.exists()
    assert "오브젝트 타입" in doc.read_text(encoding="utf-8")
    assert str(doc) in capsys.readouterr().out
