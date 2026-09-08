"""What an Android app bundle looks like from the outside.

Android apps are not one file any more. A store download is usually an archive
of archives:

* ``.apk``  — a single APK. Contains ``AndroidManifest.xml`` and ``classes*.dex``.
* ``.xapk`` — a ZIP holding a base APK plus split APKs and a ``manifest.json``.
* ``.apks`` — Google's bundle output: split APKs plus a ``toc.pb`` table of contents.

They are all ZIP files, which is why detection reads the entry list rather than
trusting the extension.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path

from apk_lens.errors import UnsupportedInputError

APK = "apk"
XAPK = "xapk"
APKS = "apks"

ZIP_MAGIC = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")

CONTAINER_DESCRIPTIONS = {
    APK: "a single APK",
    XAPK: "a bundle of split APKs with a manifest.json",
    APKS: "a bundle of split APKs with a protobuf table of contents",
}


@dataclass(frozen=True)
class ContainerInfo:
    container: str
    entry_count: int
    apk_members: tuple[str, ...]

    @property
    def description(self) -> str:
        return CONTAINER_DESCRIPTIONS[self.container]

    @property
    def is_multi_apk(self) -> bool:
        return self.container in (XAPK, APKS)


def looks_like_zip(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(4) in [magic[:4] for magic in ZIP_MAGIC]
    except OSError:
        return False


def inspect(path: Path) -> ContainerInfo:
    """Classify a downloaded or local file, or explain why it is unusable."""
    if not path.exists():
        raise UnsupportedInputError(f"no such file: {path}")
    if path.is_dir():
        raise UnsupportedInputError(
            f"{path} is a directory",
            hint="pass the .apk / .xapk / .apks file itself",
        )
    if not looks_like_zip(path):
        raise UnsupportedInputError(
            f"{path.name} is not a ZIP-based Android bundle",
            hint=(
                "APK, XAPK and APKS files are all ZIP archives. A download that "
                "starts with HTML usually means a mirror served a web page instead "
                "of the file — open the page in a browser and copy the direct link."
            ),
        )

    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile as broken:
        raise UnsupportedInputError(
            f"{path.name} is a damaged archive ({broken})",
            hint="delete it and download again; a truncated download is the usual cause",
        ) from broken

    entries = set(names)
    apk_members = tuple(sorted(name for name in names if name.lower().endswith(".apk")))

    if "AndroidManifest.xml" in entries and any(n.startswith("classes") for n in entries):
        container = APK
    elif "manifest.json" in entries and apk_members:
        container = XAPK
    elif apk_members and any(n.endswith("toc.pb") for n in names):
        container = APKS
    elif apk_members:
        # A plain ZIP of APKs. Treat it as a split bundle: the unpacker only
        # needs to know that the code lives one level down.
        container = APKS
    else:
        raise UnsupportedInputError(
            f"{path.name} is a ZIP file but contains no APK and no Android manifest",
            hint=(
                "check that the download is the app bundle itself and not, say, "
                "an OBB expansion file or a screenshot pack"
            ),
        )

    return ContainerInfo(container=container, entry_count=len(names), apk_members=apk_members)
