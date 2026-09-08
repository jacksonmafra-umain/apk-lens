"""Synthetic app bundles.

Real APKs cannot live in this repository, so the fixtures build the smallest
ZIP that is *structurally* an APK, an XAPK or an APKS. That is enough for the
unpacker and the container detector, and it keeps the test suite offline.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

MINIMAL_MANIFEST_XML = b"\x03\x00\x08\x00fake-binary-axml"
MINIMAL_DEX = b"dex\n035\x00" + b"\x00" * 32


def _write_zip(target: Path, members: dict[str, bytes]) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    return target


def build_apk(
    target: Path, *, package: str = "com.example.demo", extra: dict | None = None
) -> Path:
    members = {
        "AndroidManifest.xml": MINIMAL_MANIFEST_XML,
        "classes.dex": MINIMAL_DEX + f"https://api.{package}.example/v1".encode(),
        "resources.arsc": b"\x02\x00\x0c\x00resources",
        "META-INF/MANIFEST.MF": b"Manifest-Version: 1.0\n",
    }
    members.update(extra or {})
    return _write_zip(target, members)


@pytest.fixture
def apk_file(tmp_path: Path) -> Path:
    return build_apk(tmp_path / "demo-1.0.apk")


@pytest.fixture
def xapk_file(tmp_path: Path) -> Path:
    base = build_apk(tmp_path / "staging" / "com.example.demo.apk")
    abi_split = _write_zip(
        tmp_path / "staging" / "config.arm64_v8a.apk",
        {
            "AndroidManifest.xml": MINIMAL_MANIFEST_XML,
            "lib/arm64-v8a/libdemo.so": b"\x7fELF" + b"telemetry.example.com\x00" * 4,
        },
    )
    manifest = json.dumps(
        {
            "package_name": "com.example.demo",
            "name": "Demo",
            "version_name": "1.0",
            "version_code": "100",
            "split_apks": [
                {"file": "com.example.demo.apk", "id": "base"},
                {"file": "config.arm64_v8a.apk", "id": "config.arm64_v8a"},
            ],
        }
    ).encode()
    return _write_zip(
        tmp_path / "demo-1.0.xapk",
        {
            "manifest.json": manifest,
            "com.example.demo.apk": base.read_bytes(),
            "config.arm64_v8a.apk": abi_split.read_bytes(),
            "icon.png": b"\x89PNG\r\n\x1a\n",
        },
    )


@pytest.fixture
def apks_file(tmp_path: Path) -> Path:
    base = build_apk(tmp_path / "staging2" / "base.apk")
    return _write_zip(
        tmp_path / "demo-1.0.apks",
        {
            "toc.pb": b"\x08\x01",
            "splits/base-master.apk": base.read_bytes(),
            "splits/base-arm64_v8a.apk": base.read_bytes(),
        },
    )


@pytest.fixture
def apk_builder():
    """Build an APK fixture with extra members, for one-off scenarios."""
    return build_apk
