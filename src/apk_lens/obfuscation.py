"""Recovering configuration that was made deliberately unreadable.

Endpoint lists and feature flags sometimes ship as scrambled asset files. The
scrambling is usually weak — a single-byte XOR, or plain compression — because
its purpose is to stop casual reading rather than to withstand analysis.

Brute force would produce 256 files of noise per asset, so a candidate is kept
only when the decoded bytes are mostly printable *and* contain something worth
having: a URL, a JSON delimiter, an endpoint-shaped key. Everything reported
therefore comes with the transform and key that produced it, so a reader can
reproduce it by hand.
"""

from __future__ import annotations

import zlib
from dataclasses import asdict, dataclass
from pathlib import Path

from apk_lens import catalog

PREVIEW_CHARS = 400
PRINTABLE = set(range(0x20, 0x7F)) | {0x09, 0x0A, 0x0D}


@dataclass(frozen=True)
class Decoded:
    """One asset that turned into readable text under a simple transform."""

    source: str
    transform: str
    key: str | None
    size_bytes: int
    preview: str
    reproduce: str

    def to_dict(self) -> dict:
        return asdict(self)


def _printable_ratio(data: bytes) -> float:
    if not data:
        return 0.0
    return sum(1 for byte in data if byte in PRINTABLE) / len(data)


def _marker_score(data: bytes, markers: list[str]) -> int:
    """Weight matches by marker length: longer markers are far less accidental."""
    lowered = data.lower()
    return sum(
        lowered.count(marker.lower().encode()) * len(marker)
        for marker in markers
    )


def _is_interesting(data: bytes, markers: list[str], min_ratio: float) -> bool:
    return _printable_ratio(data) >= min_ratio and _marker_score(data, markers) > 0


def _preview(data: bytes) -> str:
    return data[:PREVIEW_CHARS].decode("utf-8", "replace").replace("\n", " ").strip()


def candidates(path: Path) -> list[Decoded]:
    """Try the cheap transforms on one asset and keep whatever becomes readable."""
    settings = catalog.load("native").get("asset_decoding", {})
    markers = settings.get("interesting_markers", ["http"])
    min_ratio = float(settings.get("min_printable_ratio", 0.85))
    max_bytes = int(settings.get("max_asset_bytes", 4 * 1024 * 1024))

    try:
        if path.stat().st_size > max_bytes:
            return []
        raw = path.read_bytes()
    except OSError:
        return []

    found: list[Decoded] = []

    # Plain text that simply was not obvious from the filename.
    if _is_interesting(raw, markers, min_ratio):
        found.append(
            Decoded(
                source=str(path),
                transform="none",
                key=None,
                size_bytes=len(raw),
                preview=_preview(raw),
                reproduce=f"cat {path.name}",
            )
        )
        return found

    # Single-byte XOR: the most common way an asset is "hidden". Every key is
    # scored and the best one wins — stopping at the first key that merely looks
    # plausible produces confident nonsense.
    best_key, best_score = None, 0
    for key in range(1, 256):
        decoded = bytes(byte ^ key for byte in raw)
        if _printable_ratio(decoded) < min_ratio:
            continue
        score = _marker_score(decoded, markers)
        if score > best_score:
            best_key, best_score = key, score

    if best_key is not None:
        decoded = bytes(byte ^ best_key for byte in raw)
        found.append(
            Decoded(
                source=str(path),
                transform="single-byte XOR",
                key=f"0x{best_key:02x}",
                size_bytes=len(decoded),
                preview=_preview(decoded),
                reproduce=(
                    f"python3 -c \"d=open('{path.name}','rb').read(); "
                    f"open('decoded.txt','wb').write(bytes(b ^ 0x{best_key:02x} for b in d))\""
                ),
            )
        )

    # Raw deflate or zlib, with or without a header.
    for label, wbits in (("zlib", 15), ("raw deflate", -15), ("gzip", 31)):
        try:
            decoded = zlib.decompress(raw, wbits)
        except (zlib.error, ValueError):
            continue
        if _is_interesting(decoded, markers, min_ratio):
            found.append(
                Decoded(
                    source=str(path),
                    transform=label,
                    key=None,
                    size_bytes=len(decoded),
                    preview=_preview(decoded),
                    reproduce=(
                        f"python3 -c \"import zlib; "
                        f"open('decoded.txt','wb').write(zlib.decompress("
                        f"open('{path.name}','rb').read(), {wbits}))\""
                    ),
                )
            )
        break

    return found


def scan_assets(paths: list[Path], *, limit: int = 40) -> list[Decoded]:
    """Try every extracted asset, stopping once ``limit`` readable ones are found."""
    results: list[Decoded] = []
    for path in paths:
        results.extend(candidates(path))
        if len(results) >= limit:
            break
    return results[:limit]
