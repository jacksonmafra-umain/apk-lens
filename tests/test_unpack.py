from __future__ import annotations

import json
from pathlib import Path

import pytest

from apk_lens import acquire, unpack
from apk_lens.cli import main
from apk_lens.errors import ApkLensError


def _workspace_for(path: Path, work: Path, **kwargs):
    return unpack.unpack(acquire.describe(path, source=str(path), kind="local"), work, **kwargs)


def test_single_apk_yields_a_base_member_with_code(apk_file: Path, tmp_path: Path):
    workspace = _workspace_for(apk_file, tmp_path / "work")
    assert [member.role for member in workspace.members] == [unpack.BASE]
    assert workspace.members[0].has_code
    assert len(workspace.dex_files) == 1
    assert workspace.base_manifest and workspace.base_manifest.exists()


def test_xapk_splits_are_classified_and_native_libs_are_found(xapk_file: Path, tmp_path: Path):
    workspace = _workspace_for(xapk_file, tmp_path / "work")
    roles = {member.role for member in workspace.members}
    assert unpack.BASE in roles
    assert unpack.ABI in roles

    abi_member = next(m for m in workspace.members if m.role == unpack.ABI)
    assert abi_member.abi == "arm64-v8a"
    # The whole point of walking the splits: the .so lives outside the base APK.
    assert any(lib.endswith("libdemo.so") for lib in workspace.native_libs)


def test_declared_metadata_is_read_from_the_bundle(xapk_file: Path, tmp_path: Path):
    workspace = _workspace_for(xapk_file, tmp_path / "work")
    assert workspace.declared["package_name"] == "com.example.demo"
    assert workspace.declared["version_name"] == "1.0"


def test_apks_bundle_is_unpacked(apks_file: Path, tmp_path: Path):
    workspace = _workspace_for(apks_file, tmp_path / "work")
    assert len(workspace.members) == 2
    assert workspace.dex_files


def test_assets_are_extracted_for_later_scanning(tmp_path: Path, apk_builder):
    apk = apk_builder(
        tmp_path / "with-assets.apk",
        extra={"assets/config/endpoints.json": b'{"host":"api.example"}'},
    )
    workspace = _workspace_for(apk, tmp_path / "work")
    assert any(name.endswith("config_endpoints.json") for name in workspace.asset_files)


def test_rerunning_reuses_the_workspace(apk_file: Path, tmp_path: Path):
    work = tmp_path / "work"
    first = _workspace_for(apk_file, work)
    marker = Path(first.root) / "marker"
    marker.write_text("kept")

    second = _workspace_for(apk_file, work)
    assert second.root == first.root
    assert marker.exists()  # reused, not rebuilt


def test_force_rebuilds_the_workspace(apk_file: Path, tmp_path: Path):
    work = tmp_path / "work"
    first = _workspace_for(apk_file, work)
    marker = Path(first.root) / "marker"
    marker.write_text("discard me")

    _workspace_for(apk_file, work, force=True)
    assert not marker.exists()


def test_workspace_slug_is_stable_and_content_addressed(apk_file: Path):
    provenance = acquire.describe(apk_file, source=str(apk_file), kind="local")
    assert unpack.slug_for(provenance).endswith(provenance.sha256[:12])


def test_missing_bundle_is_reported_clearly(apk_file: Path, tmp_path: Path):
    provenance = acquire.describe(apk_file, source=str(apk_file), kind="local")
    apk_file.unlink()
    with pytest.raises(ApkLensError, match="gone"):
        unpack.unpack(provenance, tmp_path / "work")


@pytest.mark.parametrize(
    ("name", "has_code", "expected"),
    [
        ("config.arm64_v8a", False, unpack.ABI),
        ("config.armeabi_v7a", False, unpack.ABI),
        ("config.pt", False, unpack.LANGUAGE),
        ("config.xxhdpi", False, unpack.DENSITY),
        ("base", True, unpack.BASE),
        ("split_camera_feature", True, unpack.FEATURE),
    ],
)
def test_split_names_map_to_roles(name, has_code, expected):
    role, _ = unpack.classify(name, has_code=has_code, package="com.example.demo")
    assert role == expected


def test_unpack_command_emits_json(xapk_file: Path, tmp_path: Path, capsys):
    exit_code = main(
        [
            "unpack",
            str(xapk_file),
            "--work-dir",
            str(tmp_path / "work"),
            "--apks-dir",
            str(tmp_path / "apks"),
            "--json",
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["container"] == "xapk"
    assert payload["members"]
