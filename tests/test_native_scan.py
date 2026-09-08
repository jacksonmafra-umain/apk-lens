from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from apk_lens import acquire, unpack
from apk_lens.cli import main
from apk_lens.scan import native
from conftest import build_apk, manifest_bytes


def native_bundle(tmp_path: Path) -> Path:
    """An XAPK whose ABI split carries a marker-rich library and a scrambled asset."""
    scrambled = bytes(b ^ 0x55 for b in b'{"endpoint":"https://cfg.example.com/v1"}')
    base = build_apk(
        tmp_path / "stage" / "com.example.demo.apk",
        extra={"assets/config/hidden.bin": scrambled},
    )
    abi = tmp_path / "stage" / "config.arm64_v8a.apk"
    with zipfile.ZipFile(abi, "w") as archive:
        archive.writestr("AndroidManifest.xml", manifest_bytes())
        archive.writestr(
            "lib/arm64-v8a/libmystery.so",
            b"\x7fELF\x00telemetry.example.com\x00ptrace\x00openudid\x00BoringSSL\x00"
            + b"\x00" * (2 * 1024 * 1024),
        )
        archive.writestr("lib/arm64-v8a/libflutter.so", b"\x7fELF" + b"\x00" * 1024)

    bundle = tmp_path / "demo.xapk"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("manifest.json", json.dumps({"package_name": "com.example.demo"}))
        archive.writestr("com.example.demo.apk", base.read_bytes())
        archive.writestr("config.arm64_v8a.apk", abi.read_bytes())
    return bundle


@pytest.fixture
def native_report(tmp_path: Path):
    bundle = native_bundle(tmp_path)
    provenance = acquire.describe(bundle, source=str(bundle), kind="local")
    workspace = unpack.unpack(provenance, tmp_path / "work")
    return native.scan(workspace)


def test_libraries_are_inventoried_with_abi_and_size(native_report):
    names = {lib.name for lib in native_report.libraries}
    assert names == {"libmystery.so", "libflutter.so"}
    assert native_report.abis == ["arm64-v8a"]
    assert native_report.libraries[0].name == "libmystery.so"  # largest first


def test_known_runtimes_are_named_so_a_big_file_is_not_a_mystery(native_report):
    flutter = next(lib for lib in native_report.libraries if lib.name == "libflutter.so")
    assert flutter.identified_as == "Flutter engine"


def test_unrecognised_large_libraries_are_called_out(native_report):
    assert any("were not recognised" in note for note in native_report.notes)


def test_markers_are_found_and_explained(native_report):
    mystery = next(lib for lib in native_report.libraries if lib.name == "libmystery.so")
    assert {"BoringSSL", "ptrace", "device identity"} <= set(mystery.marker_names)
    assert all(marker["meaning"] for marker in mystery.markers)


def test_markers_never_assert_intent(native_report):
    assert any("purpose is a question this method cannot answer" in n for n in native_report.notes)


def test_hosts_inside_native_code_are_surfaced(native_report):
    mystery = next(lib for lib in native_report.libraries if lib.name == "libmystery.so")
    assert "telemetry.example.com" in mystery.hosts
    assert any("invisible to a Java-only analysis" in note for note in native_report.notes)


def test_the_blind_spot_is_quantified(native_report):
    statement = native_report.opacity_statement
    assert "read as text only" in statement
    assert "largest gap" in statement
    assert 0 < native_report.native_share <= 1


def test_scrambled_assets_are_decoded(native_report):
    assert native_report.counts["decoded_assets"] == 1
    assert "cfg.example.com" in native_report.decoded_assets[0]["preview"]


def test_a_bundle_without_native_code_says_what_that_means(apk_file: Path, tmp_path: Path):
    provenance = acquire.describe(apk_file, source=str(apk_file), kind="local")
    workspace = unpack.unpack(provenance, tmp_path / "work")
    report = native.scan(workspace)
    assert "was a base APK without its ABI split" in report.opacity_statement


def test_native_command_emits_json(tmp_path: Path, capsys):
    bundle = native_bundle(tmp_path)
    exit_code = main(
        [
            "native",
            str(bundle),
            "--work-dir",
            str(tmp_path / "work"),
            "--apks-dir",
            str(tmp_path / "apks"),
            "--json",
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["opacity_statement"]
    assert payload["counts"]["libraries"] == 2
