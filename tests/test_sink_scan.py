from __future__ import annotations

import json
from pathlib import Path

import pytest

from apk_lens import catalog
from apk_lens.cli import main
from apk_lens.scan import sinks
from tests_support import FakeCorpus


@pytest.fixture
def source_corpus(tmp_path: Path) -> FakeCorpus:
    root = tmp_path / "java"
    app = root / "com" / "example" / "demo"
    sdk = root / "com" / "adjust" / "sdk"
    app.mkdir(parents=True)
    sdk.mkdir(parents=True)

    (app / "Where.java").write_text(
        "class Where {\n"
        "  void a() { manager.getLastKnownLocation(GPS); }\n"
        "  void b() { manager.requestLocationUpdates(GPS, 0, 0, this); }\n"
        "}\n"
    )
    (app / "Paste.java").write_text("class Paste {\n  void p() { clip.getPrimaryClip(); }\n}\n")
    (sdk / "Ads.java").write_text(
        "class Ads {\n  void id() { AdvertisingIdClient.getAdvertisingIdInfo(ctx); }\n}\n"
    )
    return FakeCorpus(roots=[root])


@pytest.fixture
def strings_corpus(tmp_path: Path) -> FakeCorpus:
    dump = tmp_path / "corpus" / "dex-strings.txt"
    dump.parent.mkdir(parents=True)
    dump.write_text("getLastKnownLocation\nAdvertisingIdClient\n")
    return FakeCorpus(roots=[dump], depth="strings", has_source=False)


def test_present_sinks_are_found_with_call_sites(source_corpus):
    report = sinks.scan(source_corpus)
    found = {finding.sink_id for finding in report.findings}
    assert {"last_known_location", "location_updates", "read_clipboard", "advertising_id"} <= found

    location = next(f for f in report.findings if f.sink_id == "last_known_location")
    assert location.citations[0].endswith("Where.java:2")
    assert location.confidence == sinks.CONFIDENCE_CITED


def test_bundled_sdk_hits_are_not_merged_with_the_apps_own_code(source_corpus):
    report = sinks.scan(source_corpus)
    ad_id = next(f for f in report.findings if f.sink_id == "advertising_id")
    clipboard = next(f for f in report.findings if f.sink_id == "read_clipboard")

    assert ad_id.origin_counts == {sinks.BUNDLED_SDK: 1}
    assert clipboard.origin_counts == {sinks.FIRST_PARTY: 1}
    assert any("vendor library is not the app itself" in note for note in report.notes)


def test_every_finding_carries_what_it_does_not_prove(source_corpus):
    for finding in sinks.scan(source_corpus).findings:
        assert "not evidence it runs" in finding.does_not_prove
        assert finding.proven_by


def test_absent_sinks_are_reported_rather_than_dropped(source_corpus):
    report = sinks.scan(source_corpus)
    absent = {finding.sink_id for finding in report.absent}
    assert "screen_capture" in absent
    assert any("absence is reported" in note for note in report.notes)


def test_string_depth_cannot_attribute_hits_and_says_so(strings_corpus):
    report = sinks.scan(strings_corpus)
    location = next(f for f in report.findings if f.sink_id == "last_known_location")
    assert location.origin_counts == {sinks.UNATTRIBUTED_PATH: 1}
    assert location.confidence == sinks.CONFIDENCE_STRING
    assert any("cannot be attributed" in note for note in report.notes)


def test_counts_cover_present_absent_and_call_sites(source_corpus):
    counts = sinks.scan(source_corpus).counts
    assert counts["sinks_present"] >= 4
    assert counts["sinks_absent"] > 0
    assert counts["call_sites"] >= 4


def test_findings_are_grouped_by_category(source_corpus):
    grouped = sinks.scan(source_corpus).categories
    assert "Location" in grouped
    assert {finding.sink_id for finding in grouped["Location"]} >= {"last_known_location"}


def test_every_catalog_entry_teaches_and_admits_its_limits():
    data = catalog.load("sinks")
    for name, block in data["categories"].items():
        assert block.get("label"), name
        assert block.get("why_it_matters"), name
        for sink in block["sinks"]:
            assert sink.get("id") and sink.get("pattern"), name
            assert sink.get("means"), sink["id"]
            assert sink.get("legitimate_use"), sink["id"]
            assert sink.get("proven_by"), sink["id"]


def test_sink_ids_are_unique_across_categories():
    data = catalog.load("sinks")
    ids = [sink["id"] for block in data["categories"].values() for sink in block["sinks"]]
    assert len(ids) == len(set(ids))


def test_sinks_command_emits_json(apk_file: Path, tmp_path: Path, capsys):
    exit_code = main(
        [
            "sinks",
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
    assert payload["absent"]
