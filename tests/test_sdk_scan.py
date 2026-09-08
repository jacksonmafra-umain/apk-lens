from __future__ import annotations

import json
from pathlib import Path

import pytest

from apk_lens import catalog
from apk_lens.cli import main
from apk_lens.scan import sdks
from tests_support import FakeCorpus


@pytest.fixture
def corpus_with_sdk_code(tmp_path: Path) -> FakeCorpus:
    root = tmp_path / "java"
    for package in ("com/adjust/sdk", "com/facebook/appevents", "io/flutter/embedding"):
        directory = root / package
        directory.mkdir(parents=True)
        (directory / "Entry.java").write_text(f"// package {package.replace('/', '.')}\n")
    return FakeCorpus(roots=[root])


def test_bundled_sdks_are_detected_from_their_package_paths(corpus_with_sdk_code):
    detected = {finding.sdk_id for finding in sdks.scan(corpus_with_sdk_code).findings}
    assert {"adjust", "facebook_sdk", "flutter"} <= detected


def test_code_evidence_is_treated_as_confirmed(corpus_with_sdk_code):
    finding = next(f for f in sdks.scan(corpus_with_sdk_code).findings if f.sdk_id == "adjust")
    assert finding.confidence == "confirmed"
    assert finding.citations
    assert "code:" in finding.evidence[0]


def test_a_domain_alone_is_only_a_possible_detection(tmp_path: Path):
    empty = tmp_path / "empty"
    empty.mkdir()
    report = sdks.scan(FakeCorpus(roots=[empty]), domains_seen=["amplitude.com"])
    finding = next(f for f in report.findings if f.sdk_id == "amplitude")
    assert finding.confidence == "possible"
    assert "weak on its own" in sdks.EVIDENCE_STRENGTH["host"]


def test_manifest_keys_confirm_a_vendor(tmp_path: Path):
    empty = tmp_path / "empty"
    empty.mkdir()
    report = sdks.scan(
        FakeCorpus(roots=[empty]),
        manifest_keys=["com.google.android.gms.ads.APPLICATION_ID"],
    )
    finding = next(f for f in report.findings if f.sdk_id == "admob")
    assert finding.confidence == "confirmed"
    assert "manifest meta-data" in finding.evidence[0]


def test_native_libraries_confirm_a_vendor(tmp_path: Path):
    empty = tmp_path / "empty"
    empty.mkdir()
    report = sdks.scan(
        FakeCorpus(roots=[empty]),
        native_libs=["/work/lib/arm64-v8a/libtmxprofiling.so"],
    )
    finding = next(f for f in report.findings if f.sdk_id == "threatmetrix")
    assert finding.confidence == "confirmed"


def test_an_sdk_without_matching_traffic_is_flagged_not_hidden(corpus_with_sdk_code):
    finding = next(f for f in sdks.scan(corpus_with_sdk_code).findings if f.sdk_id == "adjust")
    assert "may be bundled but unused" in finding.traffic_status


def test_vendor_domains_without_vendor_code_are_surfaced(tmp_path: Path):
    empty = tmp_path / "empty"
    empty.mkdir()
    report = sdks.scan(FakeCorpus(roots=[empty]), domains_seen=["nr-data.net"])
    # It matched the catalog host, so it is a detection *and* reconciled; the
    # unmatched list is for domains no detection claimed.
    assert any(f.sdk_id == "newrelic" for f in report.findings)
    assert report.vendor_domains_without_code == []


def test_cross_platform_frameworks_change_how_much_the_analysis_covers(corpus_with_sdk_code):
    report = sdks.scan(corpus_with_sdk_code)
    assert any("most of its logic lives outside the decompiled Java" in n for n in report.notes)


def test_detection_never_claims_the_app_sends_anything(corpus_with_sdk_code):
    notes = sdks.scan(corpus_with_sdk_code).notes
    assert any("not proof the app uses it" in note for note in notes)
    assert any("not a measurement of this app" in note for note in notes)


def test_catalog_entries_are_complete_and_documented():
    for entry in catalog.load("sdks")["sdks"]:
        assert entry.get("id") and entry.get("vendor") and entry.get("category"), entry
        assert entry.get("collects"), entry["id"]
        assert entry.get("docs", "").startswith("http"), entry["id"]
        kinds = ("packages", "classes", "manifest_keys", "native_libs", "hosts")
        assert any(entry.get(kind) for kind in kinds), entry["id"]


def test_catalog_ids_are_unique():
    ids = [entry["id"] for entry in catalog.load("sdks")["sdks"]]
    assert len(ids) == len(set(ids))


def test_sdks_command_emits_json(apk_file: Path, tmp_path: Path, capsys):
    exit_code = main(
        [
            "sdks",
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
    assert "counts" in payload
    assert payload["evidence_strength"]["package"].startswith("strong")
