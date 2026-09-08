from __future__ import annotations

import json
from pathlib import Path

from apk_lens.cli import main
from apk_lens.scan import network

SAMPLE = """
    https://api.myapp.example.com/v1/session
    https://cdn.myapp.example.com/static/a.png
    http://legacy.myapp.example.com/ping
    https://api.amplitude.com/2/httpapi
    https://graph.facebook.com/v12.0/activities
    https://app-measurement.com/a
    https://mystery.datacollect.io/ingest
    xmlns:android="http://schemas.android.com/apk/res/android"
    "http://www.w3.org/2000/svg"
"""


def report():
    return network.scan_text(SAMPLE, package="com.myapp.example")


def test_hosts_are_grouped_into_registrable_domains():
    found = {finding.domain for finding in report().findings}
    assert "example.com" in found
    assert "amplitude.com" in found


def test_first_party_is_recognised_from_the_package_name():
    finding = next(f for f in report().findings if f.domain == "example.com")
    assert finding.bucket == network.FIRST_PARTY
    assert len(finding.hosts) == 3


def test_known_vendors_are_named_with_a_purpose():
    finding = next(f for f in report().findings if f.domain == "amplitude.com")
    assert finding.bucket == network.THIRD_PARTY
    assert finding.operator == "Amplitude"
    assert finding.purpose == "analytics"
    assert finding.collects


def test_xml_namespaces_are_not_counted_as_servers():
    # The most common way a host census overstates its findings.
    buckets = {f.domain: f.bucket for f in report().findings}
    assert buckets["android.com"] == network.SPECIFICATION
    assert buckets["w3.org"] == network.SPECIFICATION


def test_unknown_domains_are_listed_first_and_never_assumed_benign():
    findings = report().findings
    assert findings[0].bucket == network.UNATTRIBUTED
    assert findings[0].domain == "datacollect.io"
    assert "highest-priority" in network.BUCKET_MEANING[network.UNATTRIBUTED]


def test_cleartext_urls_are_collected():
    result = report()
    assert any(url.startswith("http://legacy") for url in result.cleartext_urls)
    assert any("plain http:// URLs" in note for note in result.notes)


def test_every_census_states_that_a_host_is_not_a_request():
    assert any("does not prove" in note for note in report().notes)


def test_skipped_hostnames_are_counted_rather_than_hidden():
    result = network.scan_text("https://collector.example.zzunknown/x")
    assert result.rejected_unknown_tld == 1
    assert any("public_suffixes.txt" in note for note in result.notes)


def test_purpose_tally_summarises_the_relationships():
    assert report().purposes["analytics"] >= 1


def test_census_streams_from_a_corpus(apk_file: Path, tmp_path: Path):
    from apk_lens import acquire, corpus, unpack

    provenance = acquire.describe(apk_file, source=str(apk_file), kind="local")
    workspace = unpack.unpack(provenance, tmp_path / "work")
    built = corpus.build(workspace)

    result = network.scan(built, package="com.example.demo")
    assert result.host_count >= 1
    assert {"example.com", "amplitude.com"} <= {f.domain for f in result.findings}


def test_network_command_emits_json(apk_file: Path, tmp_path: Path, capsys):
    exit_code = main(
        [
            "network",
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
    assert payload["bucket_meaning"][network.UNATTRIBUTED]


def test_catalog_operators_are_well_formed():
    from apk_lens import catalog

    data = catalog.load("hosts")
    purposes = {
        "api", "cdn", "analytics", "attribution", "ads", "crash", "push", "auth",
        "payments", "antifraud", "config", "support", "infrastructure", "specification",
    }
    for entry in data["operators"]:
        assert entry.get("operator"), entry
        assert entry.get("match"), entry
        assert entry.get("purpose") in purposes, entry
