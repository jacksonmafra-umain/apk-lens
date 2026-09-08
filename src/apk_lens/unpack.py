"""Turning a bundle into a workspace the scanners can read.

A store download is an archive of archives, and the interesting parts are
spread across them:

* the **base APK** holds the code (``classes*.dex``) and the manifest;
* an **ABI split** holds the native libraries — the ``.so`` files that an
  analysis looking only at the base APK never sees;
* **language** and **density** splits hold resources;
* **feature modules** hold code that is downloaded after install.

So unpacking is not "unzip it": it is flattening a tree of archives into
predictable directories, while recording which archive each artefact came from.
Everything lands under ``work/<slug>/`` and is git-ignored.
"""

from __future__ import annotations

import json
import re
import shutil
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from apk_lens import bundles, console
from apk_lens.acquire import Provenance
from apk_lens.errors import ApkLensError

DEFAULT_WORK_DIR = Path("work")
INVENTORY_FILENAME = "inventory.json"

# Extracting a multi-gigabyte asset would defeat the purpose; assets are read
# for embedded configuration, and configuration is small.
MAX_ASSET_BYTES = 32 * 1024 * 1024

ABIS = ("arm64-v8a", "armeabi-v7a", "armeabi", "x86_64", "x86", "mips64", "mips")
DENSITIES = ("ldpi", "mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi", "tvdpi", "nodpi", "anydpi")

BASE = "base"
ABI = "abi"
LANGUAGE = "language"
DENSITY = "density"
FEATURE = "feature"
UNKNOWN = "unknown"

ROLE_MEANING = {
    BASE: "application code and manifest",
    ABI: "native libraries for one processor architecture",
    LANGUAGE: "translated resources",
    DENSITY: "images for one screen density",
    FEATURE: "an on-demand feature module",
    UNKNOWN: "unclassified split",
}

_LANGUAGE_TAG = re.compile(r"^[a-z]{2,3}(?:_[A-Za-z]{2,4})?$")


@dataclass(frozen=True)
class Member:
    """One APK inside the bundle."""

    name: str
    path: str
    role: str
    size_bytes: int
    entry_count: int
    abi: str | None = None
    has_code: bool = False

    @property
    def file(self) -> Path:
        return Path(self.path)

    @property
    def meaning(self) -> str:
        return ROLE_MEANING[self.role]


@dataclass
class Workspace:
    """Where every extracted artefact for one bundle lives."""

    root: str
    provenance: dict
    container: str
    members: list[Member] = field(default_factory=list)
    dex_files: list[str] = field(default_factory=list)
    native_libs: list[str] = field(default_factory=list)
    asset_files: list[str] = field(default_factory=list)
    manifest_files: list[str] = field(default_factory=list)
    declared: dict = field(default_factory=dict)
    signing: dict | None = None

    @property
    def path(self) -> Path:
        return Path(self.root)

    @property
    def base_manifest(self) -> Path | None:
        for candidate in self.manifest_files:
            if Path(candidate).stem.endswith(f"__{BASE}"):
                return Path(candidate)
        return Path(self.manifest_files[0]) if self.manifest_files else None

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["members"] = [asdict(member) for member in self.members]
        return payload

    @classmethod
    def from_dict(cls, payload: dict) -> Workspace:
        members = [Member(**member) for member in payload.get("members", [])]
        return cls(**{**payload, "members": members})


def slug_for(provenance: Provenance) -> str:
    """A stable directory name: readable, and unique per exact file."""
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(provenance.filename).stem).strip("-")
    return f"{stem[:60] or 'bundle'}-{provenance.sha256[:12]}"


def workspace_dir(provenance: Provenance, base_dir: Path | None = None) -> Path:
    return (base_dir or DEFAULT_WORK_DIR) / slug_for(provenance)


def classify(member_name: str, *, has_code: bool, package: str | None) -> tuple[str, str | None]:
    """Work out what a split APK is for, from its filename.

    Split naming is a convention rather than a guarantee, so the code falls
    back to ``unknown`` instead of guessing — an unclassified split still gets
    scanned, it just is not described.
    """
    stem = Path(member_name).stem
    lowered = stem.lower().replace("-", "_")

    for abi in ABIS:
        if abi.replace("-", "_") in lowered:
            return ABI, abi

    if has_code and (
        lowered in {"base", "base_master"}
        or lowered.endswith("_master")
        or (package and lowered.startswith(package.lower()))
    ):
        return BASE, None

    tail = lowered.rsplit("config_", 1)[-1] if "config_" in lowered else lowered.rsplit(".", 1)[-1]
    if tail in DENSITIES:
        return DENSITY, None
    if _LANGUAGE_TAG.match(tail):
        return LANGUAGE, None
    if has_code:
        return FEATURE if not lowered.startswith("config") else UNKNOWN, None
    return UNKNOWN, None


def _safe_extract(archive: zipfile.ZipFile, member: str, target: Path) -> Path | None:
    """Extract one entry to an explicit path, never trusting the entry name."""
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with archive.open(member) as source, target.open("wb") as sink:
            shutil.copyfileobj(source, sink)
    except (KeyError, zipfile.BadZipFile, OSError) as failure:
        console.warn(f"could not extract {member}: {failure}")
        return None
    return target


def _flat_name(entry: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", entry).strip("_")


def _harvest_apk(apk_path: Path, label: str, root: Path, workspace: Workspace) -> Member:
    """Pull the analysable parts out of one APK."""
    with zipfile.ZipFile(apk_path) as archive:
        names = archive.namelist()
        has_code = any(name.startswith("classes") and name.endswith(".dex") for name in names)
        package = (workspace.declared or {}).get("package_name")
        role, abi = classify(label, has_code=has_code, package=package)

        for entry in names:
            if entry.startswith("classes") and entry.endswith(".dex"):
                target = root / "dex" / label / Path(entry).name
                if _safe_extract(archive, entry, target):
                    workspace.dex_files.append(str(target))
            elif entry.startswith("lib/") and entry.endswith(".so"):
                target = root / "lib" / Path(entry).relative_to("lib")
                if _safe_extract(archive, entry, target):
                    workspace.native_libs.append(str(target))
            elif entry == "AndroidManifest.xml":
                target = root / "manifest" / f"{label}__{role}.xml"
                if _safe_extract(archive, entry, target):
                    workspace.manifest_files.append(str(target))
            elif entry.startswith("assets/") and not entry.endswith("/"):
                info = archive.getinfo(entry)
                if info.file_size <= MAX_ASSET_BYTES:
                    target = root / "assets" / _flat_name(entry[len("assets/"):])
                    if _safe_extract(archive, entry, target):
                        workspace.asset_files.append(str(target))

    return Member(
        name=label,
        path=str(apk_path),
        role=role,
        size_bytes=apk_path.stat().st_size,
        entry_count=len(names),
        abi=abi,
        has_code=has_code,
    )


def _read_declared(container_path: Path, info: bundles.ContainerInfo) -> dict:
    """Version and split metadata the bundle declares about itself."""
    if info.container != bundles.XAPK:
        return {}
    try:
        with zipfile.ZipFile(container_path) as archive:
            return json.loads(archive.read("manifest.json").decode("utf-8", "replace"))
    except (KeyError, ValueError, zipfile.BadZipFile):
        return {}


def unpack(
    provenance: Provenance,
    base_dir: Path | None = None,
    *,
    force: bool = False,
) -> Workspace:
    """Flatten a bundle into ``work/<slug>/`` and return its inventory.

    Re-running is a no-op: the inventory on disk is reused unless ``force``.
    """
    container_path = provenance.file
    if not container_path.exists():
        raise ApkLensError(
            f"the bundle recorded in provenance is gone: {container_path}",
            hint="run `apk-lens acquire` again",
        )

    root = workspace_dir(provenance, base_dir)
    inventory = root / INVENTORY_FILENAME
    if inventory.exists() and not force:
        try:
            console.note(f"reusing workspace {root}")
            return Workspace.from_dict(json.loads(inventory.read_text()))
        except (ValueError, TypeError):
            console.warn("workspace inventory is unreadable; unpacking again")

    if root.exists() and force:
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    info = bundles.inspect(container_path)
    workspace = Workspace(
        root=str(root),
        provenance=provenance.to_dict(),
        container=info.container,
        declared=_read_declared(container_path, info),
    )

    if info.is_multi_apk:
        staging = root / "unpacked"
        staging.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(container_path) as archive:
            for entry in info.apk_members:
                _safe_extract(archive, entry, staging / _flat_name(entry))
        apk_paths = sorted(staging.glob("*.apk"))
    else:
        apk_paths = [container_path]

    for apk_path in apk_paths:
        workspace.members.append(_harvest_apk(apk_path, apk_path.stem, root, workspace))

    workspace.members.sort(key=lambda member: (member.role != BASE, member.name))
    inventory.write_text(json.dumps(workspace.to_dict(), indent=2) + "\n")
    return workspace
