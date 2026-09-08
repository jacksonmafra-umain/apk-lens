from __future__ import annotations

from pathlib import Path

import pytest

from apk_lens import bundles
from apk_lens.errors import UnsupportedInputError


def test_single_apk_is_detected(apk_file: Path):
    info = bundles.inspect(apk_file)
    assert info.container == bundles.APK
    assert not info.is_multi_apk


def test_xapk_is_detected_with_its_split_members(xapk_file: Path):
    info = bundles.inspect(xapk_file)
    assert info.container == bundles.XAPK
    assert info.is_multi_apk
    assert "config.arm64_v8a.apk" in info.apk_members


def test_apks_is_detected(apks_file: Path):
    assert bundles.inspect(apks_file).container == bundles.APKS


def test_html_download_is_rejected_with_a_useful_hint(tmp_path: Path):
    page = tmp_path / "download.apk"
    page.write_bytes(b"<!doctype html><title>Download</title>")
    with pytest.raises(UnsupportedInputError) as raised:
        bundles.inspect(page)
    assert "not a ZIP-based Android bundle" in str(raised.value)
    assert "direct link" in raised.value.hint


def test_zip_without_android_content_is_rejected(tmp_path: Path):
    import zipfile

    archive = tmp_path / "screenshots.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("shot.png", b"\x89PNG")
    with pytest.raises(UnsupportedInputError):
        bundles.inspect(archive)


def test_missing_file_is_reported_by_name(tmp_path: Path):
    with pytest.raises(UnsupportedInputError, match="no such file"):
        bundles.inspect(tmp_path / "absent.apk")
