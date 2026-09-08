"""Pulling readable text out of compiled files.

Hostnames, API paths, permission names, SDK class names and error messages all
survive compilation as literal text inside `classes*.dex` and inside native
`.so` libraries. Extracting them is crude — it is the classic ``strings(1)``
sweep — but it needs no decompiler, finishes in seconds, and is enough to
answer "where does this app connect to?".

What it *cannot* do is show context. A hostname found this way has no call
site, so a finding from strings alone is weaker evidence than a finding with a
`file:line`. The report layer is responsible for saying which is which.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from pathlib import Path

READ_CHUNK_BYTES = 4 * 1024 * 1024

# Six is the usual floor for dex: shorter runs are mostly type descriptors.
DEX_MIN_LENGTH = 6
# Native libraries are noisier, so ask for a little more before believing it.
NATIVE_MIN_LENGTH = 8

_PRINTABLE = rb"[\x20-\x7e]"


def _pattern(min_length: int) -> re.Pattern[bytes]:
    return re.compile(_PRINTABLE + b"{" + str(min_length).encode() + b",}")


def iter_strings(path: Path, min_length: int = DEX_MIN_LENGTH) -> Iterator[str]:
    """Yield printable runs from one file, streaming so large files are fine."""
    pattern = _pattern(min_length)
    carry = b""
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(READ_CHUNK_BYTES):
                data = carry + chunk
                matches = list(pattern.finditer(data))
                # The last match may continue into the next chunk; hold it back.
                carry = b""
                if matches and matches[-1].end() == len(data):
                    carry = matches.pop().group()
                for match in matches:
                    yield match.group().decode("ascii", "replace")
    except OSError:
        return
    if carry:
        yield carry.decode("ascii", "replace")


def collect(paths: Iterable[Path], min_length: int = DEX_MIN_LENGTH) -> list[str]:
    """Deduplicated, sorted strings across several files."""
    seen: set[str] = set()
    for path in paths:
        seen.update(iter_strings(path, min_length))
    return sorted(seen)


def dump(paths: Iterable[Path], target: Path, min_length: int = DEX_MIN_LENGTH) -> int:
    """Write the deduplicated strings of ``paths`` to ``target``; return the count."""
    values = collect(paths, min_length)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(values) + ("\n" if values else ""))
    return len(values)
