from __future__ import annotations

import json
from pathlib import Path

import pytest

from apk_lens import pipeline, report
from apk_lens.cli import main
from apk_lens.commands.report import load
from apk_lens.errors import ApkLensError


def test_analyze_prints_the_headline_findings(xapk_file: Path, tmp_path: Path, capsys):
    main(
        [
            "analyze",
            str(xapk_file),
            "--work-dir",
            str(tmp_path / "work"),
            "--apks-dir",
            str(tmp_path / "apks"),
            "--out",
            str(tmp_path / "reports"),
        ]
    )
    out = capsys.readouterr().out
    for area in ("permissions", "endpoints", "sensitive APIs", "third parties", "native code"):
        assert area in out


def test_analyze_suggests_full_depth_after_a_fast_pass(xapk_file: Path, tmp_path: Path, capsys):
    main(
        [
            "analyze",
            str(xapk_file),
            "--work-dir",
            str(tmp_path / "work"),
            "--apks-dir",
            str(tmp_path / "apks"),
            "--out",
            str(tmp_path / "reports"),
        ]
    )
    assert "--depth full" in capsys.readouterr().err


def test_analyze_json_skips_the_report_and_prints_the_result(
    xapk_file: Path, tmp_path: Path, capsys
):
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
            "--json",
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["app"]["package"] == "com.example.demo"
    assert not (tmp_path / "reports").exists()


def test_no_native_skips_that_stage(xapk_file: Path, tmp_path: Path):
    result = pipeline.analyse(
        str(xapk_file),
        apks_dir=tmp_path / "apks",
        work_dir=tmp_path / "work",
        skip_native=True,
    )
    assert "native" not in result.stages_run
    assert result.native == {}


def test_completed_stages_are_journaled_so_a_run_can_say_where_it_stopped(
    xapk_file: Path, tmp_path: Path
):
    result = pipeline.analyse(
        str(xapk_file), apks_dir=tmp_path / "apks", work_dir=tmp_path / "work"
    )
    journal = pipeline.read_journal(Path(result.workspace["root"]))
    assert set(journal["stages"]) == set(result.stages_run)
    assert all("seconds" in entry for entry in journal["stages"].values())


def test_rerunning_reuses_the_expensive_stages(xapk_file: Path, tmp_path: Path, capsys):
    for _ in range(2):
        pipeline.analyse(
            str(xapk_file), apks_dir=tmp_path / "apks", work_dir=tmp_path / "work"
        )
    assert "reusing" in capsys.readouterr().err


def test_a_report_can_be_re_rendered_without_re_analysing(xapk_file: Path, tmp_path: Path):
    result = pipeline.analyse(
        str(xapk_file), apks_dir=tmp_path / "apks", work_dir=tmp_path / "work"
    )
    produced = report.write(result, tmp_path / "reports")

    exit_code = main(["report", str(produced.results_json), "--out", str(tmp_path / "again")])
    assert exit_code == 0
    assert (tmp_path / "again" / produced.root.name / "README.md").exists()


def test_a_re_rendered_report_keeps_the_original_run_metadata(xapk_file: Path, tmp_path: Path):
    result = pipeline.analyse(
        str(xapk_file),
        apks_dir=tmp_path / "apks",
        work_dir=tmp_path / "work",
        category="social",
    )
    produced = report.write(result, tmp_path / "reports")
    reloaded = load(produced.results_json)

    assert reloaded.package == result.package
    assert reloaded.category == "social"
    assert reloaded.generated_at == result.generated_at
    assert reloaded.limits() == result.limits()


def test_a_file_that_is_not_a_result_is_rejected_clearly(tmp_path: Path):
    junk = tmp_path / "notes.json"
    junk.write_text('{"hello": "world"}')
    with pytest.raises(ApkLensError, match="does not look like an apk-lens result"):
        load(junk)


def test_invalid_json_is_reported_with_a_hint(tmp_path: Path):
    junk = tmp_path / "broken.json"
    junk.write_text("{not json")
    with pytest.raises(ApkLensError, match="not valid JSON"):
        load(junk)
