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
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from apk_lens import __version__, bundles, console
from apk_lens.errors import AcquisitionError

DEFAULT_DEST = Path("apks")
HASH_CHUNK_BYTES = 1024 * 1024
DOWNLOAD_CHUNK_BYTES = 256 * 1024

# Big apps are genuinely huge; the cap exists to stop a mistyped URL from
# filling a disk, not to second-guess the app under analysis.
DEFAULT_MAX_BYTES = 3 * 1024**3
NETWORK_TIMEOUT_SECONDS = 60
USER_AGENT = f"apk-lens/{__version__} (+https://github.com/jacksonmafra-umain/apk-lens)"
HTML_CONTENT_TYPES = ("text/html", "application/xhtml")
SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._+-]+")

# Mirrors hand out a landing page rather than the file. Two hops is enough for
# every layout seen in practice (app page -> download page -> file) and keeps
# the tool from wandering around a site.
MAX_PAGE_HOPS = 2
PAGE_READ_LIMIT = 512 * 1024
# The query string is part of the link: signed CDN URLs stop working without it.
FILE_LINK = re.compile(r"""href=["']([^"']+\.(?:xapk|apks|apk)(?:\?[^"']*)?)["']""", re.I)
DOWNLOAD_LINK = re.compile(r"""href=["']([^"']*(?:/download|download=|/dl/)[^"']*)["']""", re.I)

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


def safe_filename(candidate: str, fallback: str = "download.apk") -> str:
    name = SAFE_FILENAME.sub("_", urllib.parse.unquote(candidate)).strip("._")
    return name or fallback


def _filename_for(response, url: str) -> str:
    disposition = response.headers.get("Content-Disposition", "")
    match = re.search(r'filename\*?=(?:UTF-8\'\'|")?([^";]+)', disposition)
    if match:
        return safe_filename(Path(match.group(1)).name)

    from_url = Path(urllib.parse.urlparse(url).path).name
    if from_url:
        return safe_filename(from_url)
    return "download.apk"


def _open(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        return urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT_SECONDS)  # noqa: S310
    except urllib.error.HTTPError as failure:
        raise AcquisitionError(
            f"the server answered {failure.code} {failure.reason} for {url}",
            hint="open the link in a browser and copy the direct file URL",
        ) from failure
    except (urllib.error.URLError, OSError, ValueError) as failure:
        raise AcquisitionError(f"could not reach {url}: {failure}") from failure


def _page_links(html: str, base_url: str) -> list[str]:
    """Direct file links first, then anything that looks like a download step."""
    ordered: list[str] = []
    for pattern in (FILE_LINK, DOWNLOAD_LINK):
        for match in pattern.finditer(html):
            absolute = urllib.parse.urljoin(base_url, match.group(1))
            if absolute not in ordered:
                ordered.append(absolute)
    return ordered


def _open_file(url: str):
    """Open ``url``, following mirror landing pages until a real file appears."""
    visited: list[str] = []
    current = url

    for _ in range(MAX_PAGE_HOPS + 1):
        response = _open(current)
        content_type = (response.headers.get_content_type() or "").lower()
        if not content_type.startswith(HTML_CONTENT_TYPES):
            return response

        page_url = response.geturl()
        html = response.read(PAGE_READ_LIMIT).decode("utf-8", errors="replace")
        response.close()
        visited.append(current)
        visited.append(page_url)

        candidates = [link for link in _page_links(html, page_url) if link not in visited]
        if not candidates:
            raise AcquisitionError(
                f"{page_url} is a web page and no download link could be found on it",
                hint=(
                    "open the page in a browser, start the download, then copy the "
                    "direct file URL and pass that instead"
                ),
            )
        console.note(f"following download link: {candidates[0]}")
        current = candidates[0]

    raise AcquisitionError(
        f"followed {MAX_PAGE_HOPS} pages from {url} without reaching a file",
        hint="copy the direct file URL from your browser's download list",
    )


def _stream(response, target: Path, max_bytes: int) -> int:
    total = int(response.headers.get("Content-Length") or 0)
    if total and total > max_bytes:
        raise AcquisitionError(
            f"the file is {human_size(total)}, above the {human_size(max_bytes)} limit",
            hint="raise it with --max-size if that is really the file you want",
        )

    written = 0
    partial = target.with_name(target.name + ".part")
    next_report = 0
    with partial.open("wb") as handle:
        while chunk := response.read(DOWNLOAD_CHUNK_BYTES):
            written += len(chunk)
            if written > max_bytes:
                handle.close()
                partial.unlink(missing_ok=True)
                raise AcquisitionError(
                    f"download exceeded the {human_size(max_bytes)} limit",
                    hint="raise it with --max-size if that is really the file you want",
                )
            handle.write(chunk)
            if written >= next_report:
                console.progress(written, total)
                next_report = written + 4 * 1024 * 1024
    console.progress(written, total or written, final=True)
    partial.replace(target)
    return written


def _verified_cache(target: Path) -> Provenance | None:
    """Return the recorded provenance when the file on disk still matches it."""
    record = read_provenance(target)
    if record and target.exists() and record.sha256 == sha256_file(target):
        return record
    return None


def _cached_for(url: str, dest_dir: Path) -> Provenance | None:
    name = Path(urllib.parse.urlparse(url).path).name
    if not name:
        return None
    return _verified_cache(dest_dir / safe_filename(name))


def download(url: str, dest_dir: Path, *, max_bytes: int = DEFAULT_MAX_BYTES,
             force: bool = False) -> Provenance:
    """Fetch ``url`` into ``dest_dir``, reusing an intact previous download."""
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Check the cache before touching the network: a 200 MB bundle should not be
    # re-fetched because a mirror is slow, moved the file, or is offline today.
    if not force:
        cached = _cached_for(url, dest_dir)
        if cached:
            console.note(f"reusing {cached.path} (hash matches the recorded download)")
            return cached

    with _open_file(url) as response:
        final_url = response.geturl()
        target = dest_dir / _filename_for(response, final_url)
        if target.exists() and not force:
            record = _verified_cache(target)
            if record:
                console.note(f"reusing {target} (already downloaded, hash matches)")
                return record
            console.note(f"re-downloading {target.name} (no matching hash on disk)")

        console.note(f"downloading {target.name}")
        _stream(response, target, max_bytes)

    record = describe(target, source=url, kind=DOWNLOAD, resolved_url=final_url)
    write_provenance(record)
    return record


def acquire(
    source: str,
    dest_dir: Path | None = None,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    force: bool = False,
) -> Provenance:
    """Resolve ``source`` — a local path or an ``http(s)`` URL — to a bundle on disk.

    A local file is left exactly where it is; the tool never moves or rewrites
    a user's own copy of an app.
    """
    if source.startswith(("http://", "https://")):
        record = download(
            source, dest_dir or DEFAULT_DEST, max_bytes=max_bytes, force=force
        )
        shape = bundles.CONTAINER_DESCRIPTIONS[record.container]
        console.note(f"{record.filename} — {record.size_human}, {shape}")
        console.note(f"sha256 {record.sha256}")
        return record

    path = Path(source).expanduser()
    record = describe(path, source=source, kind=LOCAL)
    write_provenance(record)
    shape = bundles.CONTAINER_DESCRIPTIONS[record.container]
    console.note(f"{record.filename} — {record.size_human}, {shape}")
    console.note(f"sha256 {record.sha256}")
    return record
