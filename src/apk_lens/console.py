"""Terminal output helpers.

Small on purpose: the project has one runtime dependency, and a progress line
plus an aligned table is the whole requirement. Colour is disabled when output
is redirected or when ``NO_COLOR`` is set, so piping stays parseable.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager

_STYLES = {
    "bold": "1",
    "dim": "2",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "cyan": "36",
}

OK = "ok"
WARN = "optional"
MISSING = "missing"

def color_enabled(stream=None) -> bool:
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return bool(getattr(stream, "isatty", lambda: False)())


def style(text: str, *names: str, stream=None) -> str:
    if not names or not color_enabled(stream):
        return text
    codes = ";".join(_STYLES[n] for n in names if n in _STYLES)
    return f"\033[{codes}m{text}\033[0m" if codes else text


def info(message: str) -> None:
    print(message)


def step(message: str) -> None:
    print(style("::", "cyan"), style(message, "bold"))


def note(message: str) -> None:
    print(style(f"   {message}", "dim"))


def warn(message: str) -> None:
    print(f"{style('warning:', 'yellow')} {message}", file=sys.stderr)


def error(message: str) -> None:
    print(f"{style('error:', 'red')} {message}", file=sys.stderr)


def render_table(headers: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    """Return a left-aligned plain-text table.

    Column widths are measured on the visible text, so pre-styled cells would
    misalign — style after layout, or pass plain strings.
    """
    materialised = [[str(cell) for cell in row] for row in rows]
    widths = [len(h) for h in headers]
    for row in materialised:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def line(cells: Sequence[str]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells)).rstrip()

    out = [style(line(headers), "bold"), style(line(["-" * w for w in widths]), "dim")]
    out.extend(line(row) for row in materialised)
    return "\n".join(out)


@contextmanager
def timed(message: str) -> Iterator[None]:
    """Announce a stage and report how long it took."""
    step(message)
    started = time.monotonic()
    try:
        yield
    finally:
        note(f"took {time.monotonic() - started:.1f}s")


def progress(done: int, total: int, *, final: bool = False) -> None:
    """Single-line transfer progress; silent when output is not a terminal."""
    if not color_enabled():
        if final:
            print(f"   {done / 1024 / 1024:.1f} MB")
        return
    if total:
        pct = min(100, int(done * 100 / total))
        line = f"   {done / 1024 / 1024:7.1f} MB / {total / 1024 / 1024:.1f} MB  {pct:3d}%"
    else:
        line = f"   {done / 1024 / 1024:7.1f} MB"
    end = "\n" if final else ""
    print(f"\r{line}", end=end, flush=True)
