from __future__ import annotations

import json
from pathlib import Path

import pytest

from apk_lens import pipeline, report
from apk_lens.cli import main
from apk_lens.errors import ApkLensError
from apk_lens.report import render
from apk_lens.results import AnalysisResult


@pytest.fixture
def rendered(tmp_path: Path, xapk_file: Path):
    result = pipeline.analyse(
        str(xapk_file),
        apks_dir=tmp_path / "apks",
        work_dir=tmp_path / "work",
        category="social",
    )
    return result, report.write(result, tmp_path / "reports")


def test_the_full_document_set_is_written(rendered):
    _, produced = rendered
    names = {path.name for path in produced.documents}
    assert names == {name for name, _ in render.DOCUMENTS}
    assert produced.readme.exists()


def test_the_report_directory_is_named_after_the_app(rendered):
    result, produced = rendered
    assert produced.root.name == f"{result.package}-{result.version_name}"


def test_every_document_states_what_it_does_not_prove(rendered):
    _, produced = rendered
    for path in produced.documents:
        assert render.LIMITS_MARKER in path.read_text(), path.name


def test_a_document_missing_its_limits_section_fails_the_render(monkeypatch, tmp_path: Path):
    """The guard exists because a findings list without caveats becomes an accusation."""
    monkeypatch.setattr(
        render, "DOCUMENTS", (("bad.md", lambda result: "# no caveats here\n"),)
    )
    with pytest.raises(ApkLensError, match="without its limits section"):
        render.write(AnalysisResult(), tmp_path / "reports")


def test_index_links_match_the_files_on_disk(rendered):
    _, produced = rendered
    readme = produced.readme.read_text()
    for path in produced.documents:
        if path.name != "README.md":
            assert f"({path.name})" in readme


def test_results_json_carries_the_whole_run(rendered):
    result, produced = rendered
    payload = json.loads(produced.results_json.read_text())
    assert payload["app"]["package"] == result.package
    assert payload["tool"]["name"] == "apk-lens"
    assert payload["limits"]
    for section in ("provenance", "workspace", "corpus", "manifest", "permissions",
                    "network", "sinks", "sdks", "native"):
        assert section in payload


def test_evidence_files_back_the_prose(rendered):
    _, produced = rendered
    names = {path.name for path in produced.evidence}
    assert {"hosts.txt", "domains.csv", "permissions.csv", "sinks.tsv"} <= names


def test_the_readme_reports_absences_as_evidence(rendered):
    _, produced = rendered
    text = produced.readme.read_text()
    assert "Absence is evidence too" in text
    assert "READ_SMS" in text


def test_the_assessment_contains_no_verdict(rendered):
    _, produced = rendered
    assessment = (produced.root / "08-assessment.md").read_text()
    assert "What this evidence cannot support" in assessment
    assert "contains no verdict" in assessment
    assert "How to close the gap" in assessment


def test_string_depth_is_disclosed_in_the_limits(rendered):
    result, _ = rendered
    assert any("--depth strings" in line for line in result.limits())


def test_a_full_depth_run_reports_failed_methods_instead(tmp_path: Path):
    result = AnalysisResult(
        corpus={"depth": "full", "java_files": 10, "decompilation": {"errors": 2400}}
    )
    limits = result.limits()
    assert any("2400 methods" in line for line in limits)
    assert not any("--depth strings" in line for line in limits)


def test_prose_is_pluralised(rendered):
    _, produced = rendered
    readme = produced.readme.read_text()
    assert "1 domain belonging" in readme or "domains belonging" in readme
    assert "1 identifiable third party" in readme or "identifiable third parties" in readme


def test_analyze_command_writes_the_set(xapk_file: Path, tmp_path: Path, capsys):
    exit_code = main(
        [
            "analyze",
            str(xapk_file),
            "--work-dir",
            str(tmp_path / "work"),
            "--apks-dir",
            str(tmp_path / "apks"),
            "--out",
            str(tmp_path / "reports"),
            "--category",
            "social",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "com.example.demo 1.0" in out
    assert "Before you quote any of it" in out
    assert (tmp_path / "reports" / "com.example.demo-1.0" / "README.md").exists()
