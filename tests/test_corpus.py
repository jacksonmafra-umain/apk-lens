from __future__ import annotations

import json
from pathlib import Path

import pytest

from apk_lens import acquire, corpus, decompile, unpack
from apk_lens.cli import main


def workspace_for(path: Path, work: Path):
    return unpack.unpack(acquire.describe(path, source=str(path), kind="local"), work)


def test_strings_depth_needs_no_decompiler(apk_file: Path, tmp_path: Path):
    built = corpus.build(workspace_for(apk_file, tmp_path / "work"))
    assert built.depth == corpus.DEPTH_STRINGS
    assert built.dex_string_count > 0
    assert Path(built.dex_strings).exists()
    assert not built.has_source


def test_native_libraries_are_scanned_separately(xapk_file: Path, tmp_path: Path):
    built = corpus.build(workspace_for(xapk_file, tmp_path / "work"))
    assert built.native_strings and Path(built.native_strings).exists()
    assert "telemetry.example.com" in Path(built.native_strings).read_text()


def test_a_bundle_without_native_libraries_says_so(apk_file: Path, tmp_path: Path):
    built = corpus.build(workspace_for(apk_file, tmp_path / "work"))
    assert any("ABI split is missing" in note for note in built.notes)


def test_string_depth_evidence_is_labelled_as_weaker(apk_file: Path, tmp_path: Path):
    built = corpus.build(workspace_for(apk_file, tmp_path / "work"))
    assert "not that a code path uses it" in built.evidence_strength


def test_search_roots_keep_the_string_dumps_at_full_depth(
    xapk_file: Path, tmp_path: Path, monkeypatch
):
    def fake_run(apk, out_dir, **kwargs):
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "Demo.java").write_text("class Demo {}\n")
        return decompile.Decompilation(
            source_dir=str(out_dir),
            apk=str(apk),
            java_files=1,
            errors=7,
            warnings=0,
            timed_out=False,
            tool_version="1.5.5",
        )

    monkeypatch.setattr(decompile, "run", fake_run)
    built = corpus.build(workspace_for(xapk_file, tmp_path / "work"), depth=corpus.DEPTH_FULL)

    assert built.has_source
    roots = [str(root) for root in built.search_roots()]
    # Native strings never appear in decompiled Java: dropping them would lose
    # every host that only exists inside a .so.
    assert built.native_strings in roots
    assert built.source_dir in roots
    assert "file:line" in built.evidence_strength


def test_failed_methods_are_reported_as_partial_coverage(
    xapk_file: Path, tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(
        decompile,
        "run",
        lambda apk, out_dir, **kwargs: decompile.Decompilation(
            source_dir=str(out_dir),
            apk=str(apk),
            java_files=0,
            errors=2400,
            warnings=12,
            timed_out=False,
            tool_version="1.5.5",
        ),
    )
    built = corpus.build(workspace_for(xapk_file, tmp_path / "work"), depth=corpus.DEPTH_FULL)
    assert any("2400 methods failed" in note for note in built.notes)


def test_a_timeout_is_reported_as_incomplete_not_as_clean(tmp_path: Path):
    result = decompile.Decompilation(
        source_dir=str(tmp_path),
        apk="base.apk",
        java_files=10,
        errors=0,
        warnings=0,
        timed_out=True,
        tool_version="1.5.5",
    )
    assert "treat absent findings as unknown" in result.coverage_note


def test_rebuilding_reuses_the_record(apk_file: Path, tmp_path: Path):
    work = tmp_path / "work"
    first = corpus.build(workspace_for(apk_file, work))
    marker = Path(first.root) / "marker"
    marker.write_text("kept")
    corpus.build(workspace_for(apk_file, work))
    assert marker.exists()


def test_an_unknown_depth_is_rejected(apk_file: Path, tmp_path: Path):
    with pytest.raises(ValueError, match="unknown depth"):
        corpus.build(workspace_for(apk_file, tmp_path / "work"), depth="deep")


def test_corpus_command_emits_json(apk_file: Path, tmp_path: Path, capsys):
    exit_code = main(
        [
            "corpus",
            str(apk_file),
            "--work-dir",
            str(tmp_path / "work"),
            "--apks-dir",
            str(tmp_path / "apks"),
            "--json",
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["depth"] == "strings"
    assert payload["search_roots"]
