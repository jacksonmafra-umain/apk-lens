"""Driving jadx, and being honest about what it could not do.

Decompilation is the slow step — tens of minutes on a large app — and it is
never complete: obfuscated, optimised or hand-written bytecode defeats every
decompiler on some methods. jadx reports those failures, and this module keeps
the count, because "we read 98% of the code" and "we read the code" are
different claims and only one of them is true.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from apk_lens import console, tools

DEFAULT_TIMEOUT_SECONDS = 3600
DEFAULT_THREADS = 8

_ERROR_COUNT = re.compile(r"finished with errors,?\s*count:\s*(\d+)", re.I)
_WARN_COUNT = re.compile(r"warnings?,?\s*count:\s*(\d+)", re.I)


@dataclass
class Decompilation:
    """The result of one jadx run, including what it failed on."""

    source_dir: str
    apk: str
    java_files: int
    errors: int
    warnings: int
    timed_out: bool
    tool_version: str | None

    @property
    def path(self) -> Path:
        return Path(self.source_dir)

    @property
    def coverage_note(self) -> str:
        if self.timed_out:
            return (
                "the decompiler was stopped by the timeout, so this source tree is "
                "incomplete: treat absent findings as unknown, not as negative"
            )
        if self.errors:
            return (
                f"{self.errors} methods failed to decompile — normal for a large "
                "obfuscated app, but it means a small part of the code was not read"
            )
        return "the decompiler reported no failures on this app"

    def to_dict(self) -> dict:
        return {**asdict(self), "coverage_note": self.coverage_note}


def run(
    apk: Path,
    out_dir: Path,
    *,
    threads: int = DEFAULT_THREADS,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    force: bool = False,
) -> Decompilation:
    """Decompile ``apk`` into ``out_dir``, reusing a previous run if present."""
    tools.require("java", "jadx")
    status = tools.find("jadx")

    existing = list(out_dir.rglob("*.java")) if out_dir.exists() else []
    if existing and not force:
        console.note(f"reusing {len(existing)} decompiled files in {out_dir}")
        return Decompilation(
            source_dir=str(out_dir),
            apk=str(apk),
            java_files=len(existing),
            errors=0,
            warnings=0,
            timed_out=False,
            tool_version=status.version,
        )

    if out_dir.exists() and force:
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    console.note(
        f"decompiling {apk.name} with jadx {status.version or '?'} — this is the slow step"
    )
    command = [
        str(status.path),
        "--no-res",
        "--no-debug-info",
        "-j",
        str(max(1, threads)),
        "-d",
        str(out_dir),
        str(apk),
    ]

    timed_out = False
    banner = ""
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            command, capture_output=True, text=True, timeout=timeout, check=False
        )
        banner = f"{completed.stdout}\n{completed.stderr}"
    except subprocess.TimeoutExpired as expired:
        timed_out = True
        banner = (expired.stdout or b"").decode("utf-8", "replace") if expired.stdout else ""
        console.warn(f"jadx hit the {timeout}s timeout; keeping what it produced")

    java_files = sum(1 for _ in out_dir.rglob("*.java"))
    errors = int(match.group(1)) if (match := _ERROR_COUNT.search(banner)) else 0
    warnings = int(match.group(1)) if (match := _WARN_COUNT.search(banner)) else 0

    return Decompilation(
        source_dir=str(out_dir),
        apk=str(apk),
        java_files=java_files,
        errors=errors,
        warnings=warnings,
        timed_out=timed_out,
        tool_version=status.version,
    )
