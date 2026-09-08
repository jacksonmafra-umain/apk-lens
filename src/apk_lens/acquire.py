"""Getting hold of the file to analyse.

There are exactly two things a user has: a file on disk, or a link. Both end up
as an :class:`Provenance` record — the same fields either way — so every later
stage, and every generated report, can state precisely *which bytes* were
analysed.

The record matters more than it looks. Reports are reproducible only if the
input is identified by content rather than by name, and the binary itself is
never committed to this repository.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from apk_lens import bundles, console
from apk_lens.errors import AcquisitionError

DEFAULT_DEST = Path("apks")
HASH_CHUNK_BYTES = 1024 * 1024

LOCAL = "local"
DOWNLOAD = "download"


@dataclass(frozen=True)
class Provenance:
    """Where the analysed bytes came from, and how to recognise them again."""

    source: str
    kind: str
    path: str
    filename: str
    size_bytes: int
    sha256: str
    container: str
    entry_count: int
    acquired_at: str
    resolved_url: str | None = None

    @property
    def file(self) -> Path:
        return Path(self.path)

    @property
    def size_human(self) -> str:
        return human_size(self.size_bytes)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> Provenance:
        known = {field: payload.get(field) for field in cls.__dataclass_fields__}
        return cls(**known)


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"  # pragma: no cover - unreachable, kept for clarity


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def provenance_path(bundle_path: Path) -> Path:
    return bundle_path.with_name(bundle_path.name + ".provenance.json")


def write_provenance(record: Provenance) -> Path:
    target = provenance_path(record.file)
    target.write_text(json.dumps(record.to_dict(), indent=2) + "\n")
    return target


def read_provenance(bundle_path: Path) -> Provenance | None:
    target = provenance_path(bundle_path)
    if not target.exists():
        return None
    try:
        return Provenance.from_dict(json.loads(target.read_text()))
    except (json.JSONDecodeError, TypeError):
        return None


def describe(path: Path, source: str, kind: str, resolved_url: str | None = None) -> Provenance:
    """Hash and classify a file that is already on disk."""
    info = bundles.inspect(path)
    return Provenance(
        source=source,
        kind=kind,
        path=str(path.resolve()),
        filename=path.name,
        size_bytes=path.stat().st_size,
        sha256=sha256_file(path),
        container=info.container,
        entry_count=info.entry_count,
        acquired_at=datetime.now(UTC).isoformat(timespec="seconds"),
        resolved_url=resolved_url,
    )


def acquire(source: str, dest_dir: Path | None = None, *, force: bool = False) -> Provenance:
    """Resolve ``source`` — a local path or an ``http(s)`` URL — to a bundle on disk.

    A local file is left exactly where it is; the tool never moves or rewrites
    a user's own copy of an app.
    """
    if source.startswith(("http://", "https://")):
        raise AcquisitionError(
            "downloading from a URL is not wired up yet",
            hint="pass a local .apk / .xapk / .apks path for now",
        )

    path = Path(source).expanduser()
    record = describe(path, source=source, kind=LOCAL)
    write_provenance(record)
    shape = bundles.CONTAINER_DESCRIPTIONS[record.container]
    console.note(f"{record.filename} — {record.size_human}, {shape}")
    console.note(f"sha256 {record.sha256}")
    return record
